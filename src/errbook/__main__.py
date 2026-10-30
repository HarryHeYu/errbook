"""支持 `python -m errbook` 直接调用，不装包也能用。"""

from .cli import main

if __name__ == "__main__":
    main()
