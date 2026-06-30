Angler Intel IL — Windows Install Instructions

Open PowerShell and paste this entire block:

# Angler Intel IL - Windows Install
# Requires: Git for Windows and Python 3.11+

cd $HOME

# Remove old folder only if you want a fresh install
# Uncomment the next line if needed:
# Remove-Item -Recurse -Force .\angler-intel-il

git clone https://github.com/jamaver/angler-intel-il.git
cd angler-intel-il

python -m venv .venv

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

pip install -r requirements.txt

python app.py

Then open a browser and go to:

http://localhost:5000

To update later, open PowerShell and run:

cd $HOME\angler-intel-il
git pull
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py

If the install fails at git clone, confirm you can open this page in a browser:

https://github.com/jamaver/angler-intel-il

If it says 404 or Repository not found, the repo is still private or the URL is different.
