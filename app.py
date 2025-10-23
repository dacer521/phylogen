from flask import Flask

def create_app(test_config=None):
	"""Create and configure the Flask application."""
	app = Flask(__name__, static_folder='static', template_folder='templates')

	# Import and register blueprints
	try:
		from phylogen.routes import bp as main_bp
		app.register_blueprint(main_bp)
	except Exception:
		@app.route('/')
		def index():
			from flask import render_template
			return render_template('index.html')

	return app


if __name__ == '__main__':
	app = create_app()
	# Use 0.0.0.0 so it is reachable from other devices if needed; debug on for development
	app.run(host='0.0.0.0', port=5000, debug=True)
