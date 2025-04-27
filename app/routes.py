from flask import Blueprint, jsonify

# Rename blueprint to avoid conflict if 'bp' is used elsewhere
main_bp = Blueprint('main', __name__)

# Example basic route under /api prefix (defined in __init__.py)
@main_bp.route('/hello')
def hello():
    """Simple health check or hello route."""
    return jsonify({"message": "Hello from Saatwik Ayurveda API!"})

# You can add other general API endpoints here if needed.
# e.g., GET /api/products (if not hardcoded in frontend)
# @main_bp.route('/products')
# def get_products():
#     # Fetch products from DB or other source
#     # products = Product.query.all()
#     # return jsonify([p.to_dict() for p in products])
#     return jsonify({"message": "Product endpoint not implemented yet."}), 501

