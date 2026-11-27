FROM public.ecr.aws/lambda/python:3.12
ENV HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 HF_HUB_DISABLE_XET=1
RUN pip install --no-cache-dir "faster-whisper==1.2.1" "av==18.1.0"
RUN HF_HUB_OFFLINE=0 python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base',local_dir='/opt/model',allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.txt'])" && echo "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9  /opt/model/model.bin" | sha256sum -c -
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py
CMD ["handler.handler"]
