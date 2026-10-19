"""选项选择状态机：四模式共用的单选/多选切换语义单一来源。

练习（PracticeSession.handle_option_click）与考试（ExamSession.select_option）
此前各写一份且语义漂移：单选重复点击同一字母，练习保持选中（用户无法取消），
考试清空选择。统一为"可取消"语义；任一侧修改只有一个定义点。
"""


def toggle_letter(current: set[str], letter: str, is_multiple: bool) -> set[str]:
    """切换 letter 的选中状态，返回新的选中集合。

    单选：点已选项 = 取消，点其他 = 改选
    多选：对称差切换（在/不在之间翻转）
    """
    if is_multiple:
        current.symmetric_difference_update({letter})
        return current
    return set() if current == {letter} else {letter}
