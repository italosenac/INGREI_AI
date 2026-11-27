FROM public.ecr.aws/lambda/python:3.12
ENV HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1
RUN pip install --no-cache-dir "faster-whisper==1.2.1"
RUN HF_HUB_OFFLINE=0 python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base',local_dir='/opt/model')"
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py
CMD ["handler.handler"]
