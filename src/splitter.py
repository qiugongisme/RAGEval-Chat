from typing import Any, List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter


class FileSplitter(RecursiveCharacterTextSplitter):
    def __init__(self, separators: Optional[List[str]] = None, **kwargs: Any) -> None:
        """Initialize a FileSplitter.

        :param separators: 自定义分隔符（支持正则）。
                          默认 ["第\\S*条 "] 匹配 "第X条 "、"第XX条 " 等条目开头，
                          传 None 或空列表则等效于 RecursiveCharacterTextSplitter 默认行为。
        """
        is_separator_regex = True
        if separators is None or len(separators) == 0:
            separators = [r"第\S*条 "]  # 使用正则表达式匹配“第X条”的开头
            is_separator_regex = True

        super().__init__(separators=separators, is_separator_regex=is_separator_regex, **kwargs)
