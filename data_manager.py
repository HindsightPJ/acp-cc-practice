from typing import List, Dict, Any, Optional, cast
import os
import sys
import json
import re
import logging
from env_utils import load_env
from telemetry import log_error

logger = logging.getLogger(__name__)

try:
    from docx import Document
except ImportError:
    Document = None


class DataLoadError(Exception):
    """题目数据加载错误"""

    pass


class DataSaveError(Exception):
    """数据保存错误"""

    pass


# ---------- parse_docx 辅助函数（TD-11: 从 parse_docx 抽取）----------


def _parse_question_header(text: str):
    """从题目行解析 (number, content)，非题目行返回 None。"""
    if not re.match(r"^\d+[\.\、．]", text):
        return None
    match = re.match(r"^(\d+)[\.\、．]\s*(.*)$", text)
    if match:
        return (int(match.group(1)), match.group(2).strip())
    return None


def _is_option_line(text: str) -> bool:
    """检测是否为选项行。"""
    return bool(re.match(r"^[•·]?\s*[A-F][\.\、\.]", text))


def _parse_option(text: str):
    """从选项行解析 (letter, text)，解析失败返回 None。"""
    match = re.match(r"^[•·]\s*([A-F])[\.\、\.]\s*(.+)$", text)
    if not match:
        match = re.match(r"^([A-F])[\.\、\.]\s+(.+)$", text)
    if not match:
        match = re.match(r"^([A-F])[\.\、\.]\t(.+)$", text)
    if match:
        return (match.group(1).upper(), match.group(2))
    return None


def _is_answer_line(text: str) -> bool:
    """检测是否为答案行。"""
    return "正确答案" in text or "答案" in text


def _parse_answer(text: str):
    """从答案行解析 answer 字符串（如 'ABC'），解析失败返回 None。"""
    answer_match = re.search(r"([A-F]+)", text)
    if answer_match:
        return answer_match.group(1).upper()
    return None


def _is_explanation_line(text: str) -> bool:
    """检测是否为解析行。"""
    return "解析" in text or "解释" in text


def _parse_explanation(text: str):
    """从解析行解析 explanation，解析失败返回 None。"""
    explanation_match = re.match(r"(?:解析|解释)[：:]\s*(.+)$", text)
    if explanation_match:
        return explanation_match.group(1)
    return None


class DataManager:
    def __init__(self, base_dir: str, user_data_dir: Optional[str] = None) -> None:
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

        # 确保用户数据目录存在
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir, exist_ok=True)

    def parse_docx(self, docx_path: str) -> List[Dict[str, Any]]:
        """解析Word文档，提取所有题目（TD-11: 检测/解析逻辑已抽取到模块级函数）。"""
        if Document is None:
            raise ImportError("请先安装python-docx库: pip install python-docx")

        doc = Document(docx_path)
        questions: List[Dict[str, Any]] = []
        current_question: Optional[Dict[str, Any]] = None

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # 检测题目编号 (如 "1." 或 "1、" 或 "1．")
            header = _parse_question_header(text)
            if header:
                if current_question:
                    questions.append(current_question)
                current_question = {
                    "number": header[0],
                    "content": header[1],
                    "options": [],
                    "answer": None,
                    "type": "single",
                    "explanation": "",
                }

            # 如果当前题目内容为空，且该段落不是选项/答案/解析，则作为题目内容
            elif (
                current_question
                and not current_question["content"]
                and not _is_option_line(text)
                and not _is_answer_line(text)
                and not _is_explanation_line(text)
            ):
                current_question["content"] = text

            # 检测选项 (A. B. C. D. E. F.) - 支持bullet前缀和Tab分隔格式
            elif current_question and _is_option_line(text):
                option = _parse_option(text)
                if option:
                    current_question["options"].append({"letter": option[0], "text": option[1]})

            # 检测正确答案（支持多选，如ABC、ABCD）
            elif current_question and _is_answer_line(text):
                answer = _parse_answer(text)
                if answer:
                    current_question["answer"] = answer
                    current_question["type"] = "multiple" if len(answer) > 1 else "single"

            # 检测解析
            elif current_question and _is_explanation_line(text):
                explanation = _parse_explanation(text)
                if explanation:
                    current_question["explanation"] = explanation

        if current_question:
            questions.append(current_question)

        # 去重：同一题号保留后出现的版本（通常是修正版）
        seen: Dict[int, Dict[str, Any]] = {}
        for q in questions:
            seen[q["number"]] = q
        questions = [seen[k] for k in sorted(seen)]

        return questions

    def load_or_parse_questions(self, docx_path: str) -> List[Dict[str, Any]]:
        """加载题目：优先读加密 questions.enc，解密失败则 fallback 到明文 questions.json → docx 解析。

        解密失败的场景（无 .env 密钥 / 密钥错误 / 文件损坏）都不阻断，
        便于他人 clone 后用自己的合法题库运行程序。

        P1-2: 打包后（frozen）禁用明文/docx fallback，避免用户篡改题库或绕过加密。
        开发模式保留 fallback，便于他人 clone 后用自己的合法题库运行程序。
        """
        # 1. 优先读加密文件
        if os.path.exists(self.questions_enc_file):
            from cryptography.fernet import InvalidToken  # TD-10: 精确捕获解密异常

            try:
                key = self._load_encryption_key()
                if key:
                    from cryptography.fernet import Fernet

                    with open(self.questions_enc_file, "rb") as f:
                        ciphertext = f.read()
                    plaintext = Fernet(key.encode()).decrypt(ciphertext)
                    return cast(List[Dict[str, Any]], json.loads(plaintext.decode("utf-8")))
            except (
                ValueError,
                OSError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                InvalidToken,
            ) as e:
                # TD-10: 收窄异常捕获——密钥格式错误(ValueError) / 文件IO(OSError) /
                # 解密失败(InvalidToken) / JSON损坏(JSONDecodeError) / 编码错误(UnicodeDecodeError)
                # → fallback，不阻断
                logger.warning("解密 questions.enc 失败，fallback 到明文: %s", e)

        # P1-2: 打包后禁用明文/docx fallback，避免用户篡改题库或绕过加密
        # 仅开发模式保留 fallback，便于他人 clone 后用自己的合法题库运行程序
        if getattr(sys, "frozen", False):
            raise DataLoadError(
                "题库密文无法解密，请通过作者重新签发注册码或重新下载程序。"
                "（打包环境不支持明文 fallback）"
            )

        # 2. fallback 明文 questions.json
        if os.path.exists(self.questions_file):
            try:
                with open(self.questions_file, "r", encoding="utf-8") as f:
                    return cast(List[Dict[str, Any]], json.load(f))
            except json.JSONDecodeError as e:
                raise DataLoadError(f"题目数据格式错误，请删除 data 文件夹后重新运行: {e}")
            except PermissionError:
                raise DataLoadError("无法读取题目文件，请检查文件权限")

        # 3. fallback docx 解析
        questions = self.parse_docx(docx_path)

        try:
            with open(self.questions_file, "w", encoding="utf-8") as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
        except PermissionError:
            raise DataSaveError(f"无法保存题目数据到 {self.questions_file}，请检查目录权限")

        return questions

    def load_meta(self) -> Optional[Dict[str, Any]]:
        """加载 questions_meta.json。

        Returns:
            元数据 dict（含 total / trial_count / version），或 None（文件不存在/损坏）
        """
        meta_path = os.path.join(self.data_dir, "questions_meta.json")
        if not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return cast(Dict[str, Any], json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def load_trial_questions(self) -> List[Dict[str, Any]]:
        """加载 questions_trial.json（前 20 题明文）。"""
        trial_path = os.path.join(self.data_dir, "questions_trial.json")
        if not os.path.exists(trial_path):
            raise DataLoadError("试用题库缺失，请重新下载程序")
        try:
            with open(trial_path, "r", encoding="utf-8") as f:
                return cast(List[Dict[str, Any]], json.load(f))
        except json.JSONDecodeError as e:
            raise DataLoadError(f"试用题库损坏，请重新下载程序: {e}")
        except PermissionError:
            raise DataLoadError("无法读取试用题库，请检查文件权限")

    def load_full_questions(self, key: str) -> List[Dict[str, Any]]:
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
            return cast(List[Dict[str, Any]], json.loads(plaintext.decode("utf-8")))
        except (ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError, InvalidToken) as e:
            # TD-10: 收窄异常捕获——密钥格式错误(ValueError) / 文件IO(OSError) /
            # 解密失败(InvalidToken) / JSON损坏(JSONDecodeError) / 编码错误(UnicodeDecodeError)
            raise DataLoadError(f"题库密文损坏或密钥不匹配: {e}")

    def _load_encryption_key(self) -> Optional[str]:
        """从 .env 读取加密密钥。

        优先读取 QUESTIONS_MASTER_KEY（新命名），兼容旧版 QUESTIONS_KEY（已弃用）。
        使用旧命名时记录弃用警告，提示用户迁移到新命名。
        """
        env = load_env(os.path.join(self.base_dir, ".env"))
        key = env.get("QUESTIONS_MASTER_KEY")
        if key is None:
            key = env.get("QUESTIONS_KEY")
            if key is not None:
                logger.warning(
                    "使用了已弃用的环境变量 QUESTIONS_KEY，请迁移到 QUESTIONS_MASTER_KEY"
                )
        return key

    def save_progress(self, progress_data: Dict[str, Any]) -> None:
        """保存学习进度（Windows 安全：先备份 .bak，再写 .tmp，最后 os.replace）"""
        tmp_file = self.progress_file + ".tmp"
        bak_file = self.progress_file + ".bak"
        try:
            # 在写入前备份现有文件（Windows 上 os.replace 非原子，崩溃时可用 .bak 恢复）
            if os.path.exists(self.progress_file):
                try:
                    os.replace(self.progress_file, bak_file)
                except OSError:
                    pass  # 备份失败不阻塞主流程
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, self.progress_file)
        except (PermissionError, OSError) as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            # 尝试从 .bak 恢复
            if os.path.exists(bak_file) and not os.path.exists(self.progress_file):
                try:
                    os.replace(bak_file, self.progress_file)
                except OSError:
                    pass
            log_error(logger, "无法保存进度数据", exc=e, progress_file=self.progress_file)
            raise DataSaveError(f"无法保存进度数据: {e}")

    def load_progress(self) -> Dict[str, Any]:
        """加载学习进度；遇到损坏文件自动备份为 .corrupt-{timestamp} 便于排查。

        若 progress.json 不存在但 .bak 存在（崩溃场景），自动从 .bak 恢复。
        """
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
            except json.JSONDecodeError as e:
                log_error(logger, "进度文件损坏，已备份", exc=e, progress_file=self.progress_file)
                self._backup_corrupt_progress()
            except PermissionError as e:
                log_error(logger, "无法读取进度文件", exc=e, progress_file=self.progress_file)
                raise DataLoadError("无法读取进度文件，请检查文件权限")

        # progress.json 不存在，尝试从 .bak 恢复（崩溃后场景）
        bak_file = self.progress_file + ".bak"
        if os.path.exists(bak_file):
            logger.warning("progress.json 缺失，尝试从 .bak 恢复")
            try:
                os.replace(bak_file, self.progress_file)
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("从 .bak 恢复失败: %s", e)

        return {
            "wrong_questions": [],
            "practice_stats": {"correct": 0, "wrong": 0, "total": 0},
            "exam_history": [],
            "favorites": [],
        }

    def _backup_corrupt_progress(self) -> None:
        """把损坏的 progress.json 改名为带时间戳的 .corrupt 副本，便于事后恢复。"""
        import time

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = f"{self.progress_file}.corrupt-{timestamp}"
        try:
            os.replace(self.progress_file, backup_path)
        except OSError:
            pass
