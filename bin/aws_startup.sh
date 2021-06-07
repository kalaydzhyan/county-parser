#!/bin/bash
yum update -y
yum install emacs -y
yum install mc -y
yum install git -y
yum install pip -y
yum install ghostscript -y

cd /tmp/
curl -O https://bootstrap.pypa.io/get-pip.py
python3 get-pip.py --user
pip install awsebcli --upgrade --user

for name in requests bs4 numpy pandas tqdm regex xldr lxml boto3; do pip install $name; done

cd /tmp/
wget https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/bin/chromedriver
curl https://intoli.com/install-google-chrome.sh | bash
mv /usr/bin/google-chrome-stable /usr/bin/google-chrome
pip install selenium
pip install webdriver-manager

yum install httpd -y
systemctl start httpd
systemctl enable httpd
cd /var/www/html
echo "Privet! This is a test page running on Apache in the AWS Cloud" > index.html
