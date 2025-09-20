FROM python:3.11-slim


# System deps for NetCDF
RUN apt-get update && apt-get install -y --no-install-recommends \
build-essential libhdf5-dev libnetcdf-dev \
&& rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


COPY app ./app
ENV STORAGE_DIR=/data/storage
RUN mkdir -p ${STORAGE_DIR}


EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]