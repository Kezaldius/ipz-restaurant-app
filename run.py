# run.py
from app import create_app
from app.api import api_bp

app = create_app()
app.register_blueprint(api_bp, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True)

