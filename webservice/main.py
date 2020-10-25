from webservice import views
from flask import Flask

app = Flask(__name__, instance_relative_config=True)
app.register_blueprint(views.bp)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=893)
