FROM python:3.13-alpine
WORKDIR /app
COPY server.py .
USER 10001:10001
EXPOSE 8000
CMD ["python", "-u", "server.py"]
