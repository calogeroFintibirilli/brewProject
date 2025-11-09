# Usa un'immagine Python ufficiale
FROM python:3.11-slim

# Imposta la directory di lavoro
WORKDIR /app

# Copia il file requirements
COPY requirements.txt .

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione e templates
COPY app.py .
COPY templates/ ./templates/

# Comando per eseguire l'applicazione (Flask)
CMD ["python", "app.py"]