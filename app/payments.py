# app/payments.py
import razorpay
import random
import hmac
import hashlib
import datetime
from flask import Blueprint, request, jsonify, current_app, g # Import g
from . import get_db
from bson import ObjectId
from .decorators import token_required # Import the token decorator

payments_bp = Blueprint('payments', __name__)

def get_razorpay_client():
    key_id = current_app.config.get('RAZORPAY_KEY_ID')
    key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
    if not key_id or not key_secret:
        raise ValueError("Razorpay API Keys are not configured.")
    return razorpay.Client(auth=(key_id, key_secret))

@payments_bp.route('/razorpay/create_order', methods=['POST'])
@token_required # Use the token decorator
def create_razorpay_order():
    """Creates a Razorpay order ID before payment attempt. Requires JWT Auth."""
    current_user_info = g.current_user
    user_id = current_user_info.get('id')
    if not user_id: return jsonify({'message': 'User ID not found in token context'}), 401

    data = request.get_json()
    if not data: return jsonify({'message': 'No input data provided'}), 400

    amount = data.get('amount')

    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({'message': 'Invalid amount provided'}), 400

    try:
        amount_in_paise = int(float(amount) * 100)
        if amount_in_paise < 100:
                return jsonify({'message': 'Amount must be at least INR 1.00'}), 400

        receipt_id = f'order_rcptid_{user_id}_{random.randint(10000, 99999)}'

        client = get_razorpay_client()
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'receipt': receipt_id,
            'payment_capture': '1' # Auto-capture
        }
        order = client.order.create(data=order_data)
        current_app.logger.info(f"Razorpay order created: {order['id']} for user {user_id}.")
        return jsonify({
            'orderId': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'keyId': current_app.config['RAZORPAY_KEY_ID']
            }), 200
    except ValueError as ve:
        current_app.logger.error(f"Razorpay config error: {str(ve)}")
        return jsonify({'message': 'Payment gateway config error', 'error': str(ve)}), 500
    except Exception as e:
        current_app.logger.error(f"Razorpay order creation failed: {str(e)}")
        return jsonify({'message': 'Could not create payment order', 'error': str(e)}), 500


# --- Webhook does NOT require user authentication/token ---
@payments_bp.route('/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
    """Handles incoming webhook events from Razorpay for payment confirmation."""
    webhook_body = request.data
    webhook_signature = request.headers.get('X-Razorpay-Signature')
    webhook_secret = current_app.config.get('RAZORPAY_WEBHOOK_SECRET')

    if not webhook_secret:
            current_app.logger.error("Rzp webhook secret not configured!")
            return jsonify({'status': 'error', 'message': 'Internal config error'}), 500
    if not webhook_signature:
        current_app.logger.warning("Webhook received without signature.")
        return jsonify({'status': 'error', 'message': 'Signature missing'}), 400

    # --- Verify Webhook Signature ---
    try:
        # --- FIXED: Added the actual HMAC verification logic ---
        generated_signature = hmac.new(
            bytes(webhook_secret, 'utf-8'),
            webhook_body,
            hashlib.sha256
        ).hexdigest()
        # --- End Fix ---

        if not hmac.compare_digest(generated_signature, webhook_signature):
                current_app.logger.error("Webhook signature verification failed.")
                return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400
    except Exception as e:
        current_app.logger.error(f"Webhook signature verification error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Signature verification error'}), 500

    # --- Process Verified Webhook Event ---
    try:
        event_data = request.get_json()
        event_type = event_data.get('event')
        current_app.logger.info(f"Received verified Rzp webhook event: {event_type}")

        db = get_db() # Get DB connection

        if event_type == 'payment.captured':
            payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
            razorpay_order_id = payment_entity.get('order_id')
            razorpay_payment_id = payment_entity.get('id')
            status = payment_entity.get('status')

            if razorpay_order_id and status == 'captured':
                order = db.orders.find_one({'razorpay.orderId': razorpay_order_id})
                if order and order.get('paymentStatus') not in ['completed', 'failed', 'refunded']:
                    update_result = db.orders.update_one(
                        {'_id': order['_id']},
                        {'$set': {
                            'paymentStatus': 'completed',
                            'razorpay.paymentId': razorpay_payment_id,
                            'razorpay.webhookVerifiedAt': datetime.datetime.utcnow()
                        }}
                    )
                    if update_result.modified_count > 0:
                            current_app.logger.info(f"Webhook: Order {str(order['_id'])} marked 'completed'.")
                    else:
                            current_app.logger.warning(f"Webhook: Order {str(order['_id'])} found but not updated (status: {order.get('paymentStatus')}).")
                elif order:
                        current_app.logger.warning(f"Webhook: Order {str(order['_id'])} already processed (status: {order.get('paymentStatus')}).")
                else:
                        current_app.logger.error(f"Webhook: Order not found for Rzp Order ID: {razorpay_order_id}")
            else:
                    current_app.logger.warning(f"Webhook: payment.captured event invalid: {payment_entity}")

        elif event_type == 'payment.failed':
            payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
            razorpay_order_id = payment_entity.get('order_id')
            razorpay_payment_id = payment_entity.get('id') # Get payment ID even on failure

            if razorpay_order_id:
                    order = db.orders.find_one({'razorpay.orderId': razorpay_order_id})
                    if order and order.get('paymentStatus') not in ['completed', 'failed', 'refunded']:
                        # --- FIXED: Added the actual $set dictionary ---
                        update_result = db.orders.update_one(
                                {'_id': order['_id']},
                                {'$set': {
                                    'paymentStatus': 'failed',
                                    'razorpay.paymentId': razorpay_payment_id, # Store payment ID
                                    'razorpay.webhookVerifiedAt': datetime.datetime.utcnow()
                                }}
                        )
                        # --- End Fix ---
                        if update_result.modified_count > 0:
                            current_app.logger.info(f"Webhook: Order {str(order['_id'])} marked 'failed'.")
                        else:
                                current_app.logger.warning(f"Webhook: Failed payment order {str(order['_id'])} found but not updated.")
                    elif order:
                        current_app.logger.warning(f"Webhook: Failed payment order {str(order['_id'])} already processed.")
                    else:
                        current_app.logger.error(f"Webhook: Order not found for failed Rzp Order ID: {razorpay_order_id}")
            else:
                current_app.logger.warning(f"Webhook: payment.failed event missing order_id.")

        # Add handling for other events if needed (e.g., refunds)

    except Exception as e:
        current_app.logger.error(f"Error processing webhook payload: {str(e)}")
        return jsonify({'status': 'error processing payload'}), 200 # Ack receipt

    return jsonify({'status': 'ok'}), 200
