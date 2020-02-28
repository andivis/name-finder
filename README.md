# name finder

## Installation

1. Make sure Python 3.8 or higher and git are installed.

    Windows:

    https://www.python.org/downloads/windows/

    If the installer asks to add Python to the path, check yes.

    https://git-scm.com/download/win

    MacOS:

    Open Terminal. Paste the following commands and press enter.

    ```
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    echo 'export PATH="/usr/local/opt/python/libexec/bin:$PATH"' >> ~/.profile
    brew install python
    ```

    Linux:

    Open a terminal window. Paste the following commands and press enter.

    ```
    sudo apt install -y python3
    sudo apt install -y python3-pip
    sudo apt install -y git
    ```

2. Open a terminal/command prompt window. Depending on your system you may need run `pip` instead of `pip3`.

```
git clone https://github.com/andivis/name-finder
cd name-finder
pip3 install -r requirements.txt
```

## Instructions

1. Make sure `user-data/input/input.csv` contains the list of url's.
2. Optionally, put your proxy list into `user-data/proxies.csv`. The header must contain `url,port,username,password`. The other lines follow that format.
3. Run `python3 main.py`. Depending on your system you may need run `python main.py` instead.
4. The output will be in `user-data/output/output.csv`.
5. If any items fail due to a captcha or other network error, the script will loop until all items are complete.

## Options

`user-data/options.ini` accepts the following options:

- `secondsBetweenLines`: Wait this many seconds after each line. Default: `0`