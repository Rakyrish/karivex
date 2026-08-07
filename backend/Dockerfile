FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput --upload-unhashed-files
EXPOSE 8000
# --timeout 300, not gunicorn's 30s default.
#
# The AI content endpoints are legitimately slow: one product costs an
# identifier lookup plus two model calls plus an optional rewrite pass, which
# runs 30-90 seconds. At the default the worker was killed mid-request and the
# admin showed "Something went wrong" even though the OpenAI calls had all
# returned 200 — the work was done and then thrown away.
#
# --graceful-timeout matches so a worker being recycled is given the same
# allowance to finish the request it is holding.
CMD ["gunicorn", "karivex.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "300", "--graceful-timeout", "300"]
