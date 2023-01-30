You can start the playground(port=80) and the bff (port=8080) locally:
```bash
python deployment/bff/app/app.py
streamlit run deployment/playground/playground.py --server.port 80
```