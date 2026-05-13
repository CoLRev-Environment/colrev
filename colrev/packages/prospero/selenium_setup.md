# Project Setup Instructions

## Prerequisites

1. **Install Google Chrome** (in Codespaces):

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
then
sudo dpkg -i google-chrome-stable_current_amd64.deb

sudo apt-get install -f

google-chrome --version
```
Google Chrome 131.0.6778.85

2. **You do NOT have to install Chromedriver(it should be already installed)**

```bash
wget https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.85/linux64/chromedriver-linux64.zip
```

3. Run the script:

```bash
pip install selenium

python3 /workspaces/colrev/colrev/packages/prospero/selenium_test.py
google-chrome --version
/workspaces/colrev/colrev/packages/prospero/bin/chromedriver --version
```
