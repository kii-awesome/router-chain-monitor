FROM python:3.8-slim
WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y gcc
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
ENV CONFIG_FILE_PATH /usr/src/app/config.yml
CMD ["python", "./main.py", "--config", "config.yml"]