# -*- coding: utf-8 -*-
"""docx_engine — req-op-manual 版式引擎统一入口。

内容脚本与构建脚本统一使用：

    from docx_engine import (
        new_document, setup_page, para, h1, h2, h3, h4, table, figure,
        steps, bullets, note, placeholder, set_run,
        cover_simple, info_block, revision_simple, toc_static, toc_page,
        header_text, footer_page,
        corporate_margins, corporate_header, corporate_footer,
        corporate_cover, corporate_revision,
        reset_fig_counters, page_field, toc_field,
    )
"""
from docx_core import *          # noqa: F401,F403
from docx_layout import *        # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith('_')]
