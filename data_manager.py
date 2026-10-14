from typing import Any, cast
import os
import json
import logging
import threading
from logging_utils import log_error
from models import Question

logger = logging.getLogger(__name__)


class DataLoadError(Exception):
    """题目数据加载错误"""

    pass


class DataSaveError(Exception):
    """数据保存错误"""

    pass


def default_progress() -> dict[str, Any]:
    """progress.json 的默认结构。

    单一来源：load_progress 的损坏回退与 AppState._ensure_defaults 都从这里取，
    避免两处默认 dict 漂移。
    """
    return {
        "wrong_questions": [],
        "practice_stats": {"correct": 0, "wrong": 0, "total": 0},
        "exam_history": [],
        "favorites": [],
        # 练习会话快照（进度恢复用）：{queue, index, answers, shuffle}
        "practice_progress": {},
        # UI 主题模式（"light" / "dark"，非法值由 AppState fail-safe 回浅色）
        "theme_mode": "light",
    }


class DataManager:
    def __init__(self, base_dir: str, user_data_dir: str | None = None) -> None:
        """初始化数据管理器。

        Args:
            base_dir: 只读题库目录（打包后=_MEIPASS，开发=源码目录）。
                      questions.enc / questions_trial.json / questions_meta.json 从此目录读。
            user_data_dir: 可写用户数据目录（progress.json / license.dat / app.log）。
                           默认 = base_dir/data（开发模式），打包后应传 exe同级/data/。
        """
        self.base_dir: str = base_dir
        self.data_dir: str = os.path.join(base_dir, "data")  # 只读题库目录
        # user_data_dir: 可写用户数据目录，默认 = data_dir（开发模式）
        self.user_data_dir: str = user_data_dir or self.data_dir
        # questions.json（docx 解析后的明文缓存）写到可写目录
        self.questions_file: str = os.path.join(self.user_data_dir, "questions.json")
        self.questions_enc_file: str = os.path.join(self.data_dir, "questions.enc")
        self.progress_file: str = os.path.join(self.user_data_dir, "progress.json")
        self._save_lock = threading.Lock()

        # 确保用户数据目录存在
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir, exist_ok=True)

    def load_meta(self) -> dict[str, Any] | None:
        """加载 questions_meta.json。

        Returns:
            元数据 dict（含 total / trial_count / version），或 None（文件不存在/损坏）
        """
        meta_path = os.path.join(self.data_dir, "questions_meta.json")
        if not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def load_trial_questions(self) -> list[Question]:
        """加载 questions_trial.json（前 20 题明文）。"""
        trial_path = os.path.join(self.data_dir, "questions_trial.json")
        if not os.path.exists(trial_path):
            raise DataLoadError("试用题库缺失，请重新下载程序")
        try:
            with open(trial_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
        except json.JSONDecodeError as e:
            raise DataLoadError(f"试用题库损坏，请重新下载程序: {e}") from e
        except PermissionError as e:
            raise DataLoadError("无法读取试用题库，请检查文件权限") from e

        questions: list[Question] = []
        for i, q in enumerate(raw_list):
            try:
                questions.append(Question.from_dict(q))
            except (ValueError, TypeError, KeyError) as e:
                raise DataLoadError(f"第{i + 1}题解析失败: {e}") from e
        return questions

    def load_full_questions(self, key: str) -> list[Question]:
        """用 K 解密 questions.enc 加载全库。

        Args:
            key: Fernet key（base64 字符串）

        Returns:
            全库题目列表

        Raises:
            DataLoadError: 解密失败或题库损坏
        """
        if not os.path.exists(self.questions_enc_file):
            raise DataLoadError("题库密文缺失，请重新下载程序")
        from cryptography.fernet import Fernet, InvalidToken  # TD-10: 精确捕获

        try:
            fernet = Fernet(key.encode())
            with open(self.questions_enc_file, "rb") as f:
                ciphertext = f.read()
            plaintext = fernet.decrypt(ciphertext)
            raw_list = json.loads(plaintext.decode("utf-8"))
        except (ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError, InvalidToken) as e:
            # TD-10: 收窄异常捕获——密钥格式错误(ValueError) / 文件IO(OSError) /
            # 解密失败(InvalidToken) / JSON损坏(JSONDecodeError) / 编码错误(UnicodeDecodeError)
            raise DataLoadError(f"题库密文损坏或密钥不匹配: {e}") from e

        questions: list[Question] = []
        for i, q in enumerate(raw_list):
            try:
                questions.append(Question.from_dict(q))
            except (ValueError, TypeError, KeyError) as e:
                raise DataLoadError(f"第{i + 1}题解析失败: {e}") from e
        return questions

    def save_progress(self, progress_data: dict[str, Any]) -> None:
        """保存学习进度（Windows 安全：先备份 .bak，再写 .tmp，最后 os.replace）"""
        with self._save_lock:
            tmp_file = self.progress_file + ".tmp"
            bak_file = self.progress_file + ".bak"
            try:
                # 在写入前备份现有文件（Windows 上 os.replace 非原子，崩溃时可用 .bak 恢复）
                if os.path.exists(self.progress_file):
                    try:
                        os.replace(self.progress_file, bak_file)
                    except OSError as backup_err:
                        # 备份失败不阻塞主流程，但留痕便于排查（静默失败零容忍）
                        logger.debug("进度备份失败: %s", backup_err)
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_file, self.progress_file)
            except (PermissionError, OSError) as e:
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except OSError as cleanup_err:
                        logger.debug("临时进度文件清理失败: %s", cleanup_err)
                # 尝试从 .bak 恢复
                if os.path.exists(bak_file) and not os.path.exists(self.progress_file):
                    try:
                        os.replace(bak_file, self.progress_file)
                    except OSError as restore_err:
                        logger.debug("进度备份恢复失败: %s", restore_err)
                log_error(logger, "无法保存进度数据", exc=e, progress_file=self.progress_file)
                raise DataSaveError(f"无法保存进度数据: {e}") from e

    def load_progress(self) -> dict[str, Any]:
        """加载学习进度；遇到损坏文件自动备份为 .corrupt-{timestamp} 便于排查。

        若 progress.json 不存在但 .bak 存在（崩溃场景），自动从 .bak 恢复。
        """
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # P2-7: 校验根节点为 dict，避免被篡改为 list/str 后 AppState 崩溃
                if not isinstance(data, dict):
                    raise json.JSONDecodeError(
                        f"进度文件根节点应为对象，实际为 {type(data).__name__}", "", 0
                    )
                return cast(dict[str, Any], data)
            except json.JSONDecodeError as e:
                log_error(logger, "进度文件损坏，已备份", exc=e, progress_file=self.progress_file)
                self._backup_corrupt_progress()
            except PermissionError as e:
                log_error(logger, "无法读取进度文件", exc=e, progress_file=self.progress_file)
                raise DataLoadError("无法读取进度文件，请检查文件权限") from e

        # progress.json 不存在，尝试从 .bak 恢复（崩溃后场景）
        bak_file = self.progress_file + ".bak"
        if os.path.exists(bak_file):
            logger.warning("progress.json 缺失，尝试从 .bak 恢复")
            try:
                os.replace(bak_file, self.progress_file)
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # P2-7: 同样校验 .bak 恢复的数据
                if not isinstance(data, dict):
                    raise json.JSONDecodeError(
                        f"备份文件根节点应为对象，实际为 {type(data).__name__}", "", 0
                    )
                return cast(dict[str, Any], data)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("从 .bak 恢复失败: %s", e)

        return default_progress()

    def _backup_corrupt_progress(self) -> None:
        """把损坏的 progress.json 改名为带时间戳的 .corrupt 副本，便于事后恢复。"""
        import time

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = f"{self.progress_file}.corrupt-{timestamp}"
        try:
            os.replace(self.progress_file, backup_path)
        except OSError as e:
            # 备份失败不阻断主流程（随后返回默认进度），但必须留痕便于排查
            logger.warning("损坏进度文件备份失败: %s | path=%s", e, self.progress_file)
