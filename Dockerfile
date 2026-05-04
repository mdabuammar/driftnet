# Read the doc: https://huggingface.co/docs/hub/spaces-sdks-docker
# you will also find guides on how best to write your Dockerfile

FROM python:3.11-slim

# The two following lines are required to run on Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt .

# Install requirements (avoids caching to save space)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the app directory and other necessary files
COPY --chown=user app/ app/
# Assuming models are downloaded dynamically or stored in a specific location
# If models are tracked by Git LFS or handled by HF, they will be available.

# Expose port 7860, which is required by Hugging Face Spaces
EXPOSE 7860

# Run the FastAPI server on the required port
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
