FROM python:3.12-slim
WORKDIR /app
COPY ad_studio ./ad_studio
ENV PYTHONUNBUFFERED=1 STUDIO_HOST=0.0.0.0 STUDIO_PORT=8787
EXPOSE 8787
# Refuses to start without STUDIO_PASSWORD (see ad_studio/server.py).
CMD ["python", "-m", "ad_studio.server"]
