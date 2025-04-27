# backend/app/orders.py
from flask import Blueprint, request, jsonify, current_app, g # Import g
import razorpay
from . import get_db
from .payments import get_razorpay_client # Keep if needed
from bson import ObjectId
import datetime
from .decorators import token_required # Import the token decorator

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/create', methods=['POST'])
@token_required # Use the token decorator
def create_order():
    """Creates an order (COD/Razorpay) in MongoDB, requires JWT auth."""
    db = get_db()
    data = request.get_json()
    if not data: return jsonify({'message': 'No input data provided'}), 400

    current_user_info = g.current_user
    user_id = current_user_info.get('id')
    if not user_id:
        return jsonify({'message': 'User ID not found in token context'}), 401

    current_app.logger.info(f"Create Order route accessed by User ID: {user_id}")

    cart_items_data = data.get('cart')
    payment_method = data.get('paymentMethod')
    address_data = data.get('address')
    razorpay_details = data.get('razorpayDetails')

    # --- Validation ---
    if not cart_items_data or not payment_method or not address_data:
        return jsonify({'message': 'Missing order details'}), 400
    if not isinstance(cart_items_data, list) or not cart_items_data:
        return jsonify({'message': 'Cart items must be a non-empty list'}), 400
    if payment_method not in ['cod', 'razorpay']:
        return jsonify({'message': 'Invalid payment method specified'}), 400
    if payment_method == 'razorpay' and not razorpay_details:
        return jsonify({'message': 'Missing Razorpay payment details'}), 400
    if not isinstance(address_data, dict):
        return jsonify({'message': 'Invalid address format'}), 400


    # --- Prepare Order Items & Calculate Total ---
    total_amount = 0
    order_items = []
    try:
        for item_data in cart_items_data:
            price = float(item_data.get('price', 0))
            quantity = int(item_data.get('quantity', 0))
            product_id = item_data.get('id')
            product_name = item_data.get('name')

            if price <= 0 or quantity <= 0 or product_id is None or not product_name:
                return jsonify({'message': f"Invalid data for item: {item_data.get('name', 'Unknown')}"}), 400

            total_amount += price * quantity
            order_items.append({
                'productId': product_id,
                'productName': product_name,
                'quantity': quantity,
                'price': price
            })
    except (ValueError, TypeError) as e:
        return jsonify({'message': 'Invalid cart item data format', 'error': str(e)}), 400
    if total_amount <= 0:
        return jsonify({'message': 'Cannot create order with zero total'}), 400

    # --- Build Order Document ---
    order_doc = {
        'userId': ObjectId(user_id),
        'totalAmount': round(total_amount, 2),
        'paymentMethod': payment_method,
        'paymentStatus': 'pending',
        'orderDate': datetime.datetime.utcnow(),
        'shippingAddress': {
            'line1': address_data.get('line1'),
            'line2': address_data.get('line2'),
            'city': address_data.get('city'),
            'state': address_data.get('state'),
            'postalCode': address_data.get('postalCode'),
            'country': address_data.get('country'),
            'phone': address_data.get('phone'),
        },
        'items': order_items,
        'razorpay': {}
    }

    # --- Payment Method Specific Logic ---
    if payment_method == 'cod':
        order_doc['paymentStatus'] = 'processing'
        current_app.logger.info(f"Preparing COD order for user {user_id}.")
    elif payment_method == 'razorpay':
        try:
            client = get_razorpay_client()
            razorpay_order_id = razorpay_details.get('orderId')
            razorpay_payment_id = razorpay_details.get('paymentId')
            razorpay_signature = razorpay_details.get('signature')

            if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
                return jsonify({'message': 'Incomplete Razorpay details'}), 400

            # --- FIXED: Added the actual parameters dictionary ---
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            # --- End Fix ---

            client.utility.verify_payment_signature(params_dict)
            current_app.logger.info(f"Frontend Rzp signature verified for order {razorpay_order_id}.")

            # Optional: Double check amount against Razorpay payment if needed
            # payment_info = client.payment.fetch(razorpay_payment_id)
            # expected_amount_paise = int(round(total_amount * 100))
            # if payment_info['amount'] != expected_amount_paise: ... handle mismatch ...

            order_doc['paymentStatus'] = 'completed' # Tentative status
            order_doc['razorpay'] = {
                'orderId': razorpay_order_id,
                'paymentId': razorpay_payment_id,
                'signature': razorpay_signature # Store for reference
            }
        except razorpay.errors.SignatureVerificationError:
            current_app.logger.error(f"Rzp signature verification FAILED for order {razorpay_details.get('orderId')}")
            return jsonify({'message': 'Payment verification failed'}), 400
        except ValueError as ve: # Catch missing Razorpay keys error
            current_app.logger.error(f"Razorpay config error: {str(ve)}")
            return jsonify({'message': 'Razorpay config error'}), 500
        except Exception as e:
            current_app.logger.error(f"Error during Rzp processing: {str(e)}")
            return jsonify({'message': 'Payment processing error'}), 500

    # --- Save Order to MongoDB ---
    try:
        result = db.orders.insert_one(order_doc)
        order_id = str(result.inserted_id)
        current_app.logger.info(f"Order {order_id} saved successfully (Status: {order_doc['paymentStatus']}).")
        return jsonify({
            'message': 'Order placed successfully!',
            'orderId': order_id,
            'status': order_doc['paymentStatus']
        }), 201
    except Exception as e:
        current_app.logger.error(f"Failed to save order: {str(e)}")
        return jsonify({'message': 'Failed to save order', 'error': str(e)}), 500


@orders_bp.route('/my-orders', methods=['GET'])
@token_required # Use the token decorator
def get_my_orders():
    """Fetches orders for the currently authenticated user via JWT."""
    db = get_db()
    current_user_info = g.current_user # Access user dict from g
    user_id = current_user_info.get('id')
    if not user_id: return jsonify({'message': 'User ID not found in token context'}), 401

    try:
        user_id_obj = ObjectId(user_id)
        user_orders_cursor = db.orders.find({'userId': user_id_obj}).sort('orderDate', -1)

        orders_list = []
        for order in user_orders_cursor:
            order['id'] = str(order.pop('_id')) # Rename _id
            order['userId'] = str(order['userId']) # Convert userId
            if 'orderDate' in order and isinstance(order['orderDate'], datetime.datetime):
                order['orderDate'] = order['orderDate'].isoformat()
            orders_list.append(order)

        return jsonify(orders_list), 200
    except (ObjectId.InvalidId, Exception) as e:
        current_app.logger.error(f"Error fetching orders for user {user_id}: {str(e)}")
        return jsonify({'message': 'Could not retrieve orders', 'error': str(e)}), 500


@orders_bp.route('/<string:order_id>', methods=['GET'])
@token_required # Use the token decorator
def get_order_details(order_id):
    """Fetches details for a specific order, ensuring it belongs to the user via JWT."""
    db = get_db()
    current_user_info = g.current_user # Access user dict from g
    user_id = current_user_info.get('id')
    if not user_id: return jsonify({'message': 'User ID not found in token context'}), 401

    try:
        order_id_obj = ObjectId(order_id)
        user_id_obj = ObjectId(user_id)

        order = db.orders.find_one({'_id': order_id_obj, 'userId': user_id_obj})

        if not order:
            return jsonify({'message': 'Order not found or access denied'}), 404

        # Format for JSON response
        order['id'] = str(order.pop('_id'))
        order['userId'] = str(order['userId'])
        if 'orderDate' in order and isinstance(order['orderDate'], datetime.datetime):
            order['orderDate'] = order['orderDate'].isoformat()

        return jsonify(order), 200
    except ObjectId.InvalidId:
        return jsonify({'message': 'Invalid Order ID format'}), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching details for order {order_id}: {str(e)}")
        return jsonify({'message': 'Could not retrieve order details', 'error': str(e)}), 500

