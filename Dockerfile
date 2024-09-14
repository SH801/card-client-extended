FROM uisautomation/python:3.8-alpine

WORKDIR /usr/src/app

# Install specific requirements for the package.
ADD requirements.txt ./
RUN pip3 install tox && pip3 install -r requirements.txt

# Copy application source and install it. Use "-e" to avoid needlessly copying
# files into the site-packages directory.
ADD ./ ./
RUN pip3 install -e .

ENTRYPOINT ["cardclientplus"]
