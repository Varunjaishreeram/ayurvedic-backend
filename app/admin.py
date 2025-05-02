# backend/app/admin.py
from flask import Blueprint, jsonify, current_app, request, g
from . import get_db
from bson import ObjectId
from .decorators import admin_required # Import the admin decorator
import datetime # Import datetime

admin_bp = Blueprint('admin', __name__)

# Allowed order statuses for validation (customize as needed)
ALLOWED_ORDER_STATUSES = ['processing', 'pending', 'shipped', 'delivered', 'completed', 'cancelled', 'failed']

# === User Management Routes ===

@admin_bp.route('/users/count', methods=['GET'])
@admin_required
def get_user_count():
    """Returns the total number of registered users."""
    db = get_db()
    try:
        count = db.users.count_documents({})
        return jsonify({'count': count}), 200
    except Exception as e:
        current_app.logger.error(f"Error counting users: {str(e)}")
        return jsonify({'message': 'Error fetching user count'}), 500

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    """Returns a list of all registered users (excluding passwords)."""
    db = get_db()
    try:
        # Exclude password_hash and sort by creation date
        users_cursor = db.users.find({}, {'password_hash': 0}).sort('created_at', -1)
        users_list = []
        for user in users_cursor:
            user['_id'] = str(user['_id']) # Convert ObjectId to string
            # Format dates if they exist
            if 'created_at' in user and isinstance(user['created_at'], datetime.datetime):
                 user['created_at'] = user['created_at'].isoformat()
            users_list.append(user)
        return jsonify(users_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all users: {str(e)}")
        return jsonify({'message': 'Error fetching users'}), 500

@admin_bp.route('/users/<string:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Deletes a specific user."""
    db = get_db()
    admin_user_id = g.current_user.get('id') # Get admin's own ID from token context

    if not user_id:
        return jsonify({'message': 'User ID is required'}), 400

    if user_id == admin_user_id:
         return jsonify({'message': 'Admin cannot delete their own account'}), 403

    try:
        user_id_obj = ObjectId(user_id)
        # Optional: Find user first to log details before deleting
        user_to_delete = db.users.find_one({'_id': user_id_obj}, {'username': 1})
        if not user_to_delete:
            return jsonify({'message': 'User not found'}), 404

        result = db.users.delete_one({'_id': user_id_obj})

        if result.deleted_count == 1:
            username = user_to_delete.get('username', 'Unknown')
            current_app.logger.info(f"Admin {admin_user_id} deleted user {username} ({user_id})")
            # Consider related actions: deleting user's orders? Or anonymizing them? For now, just delete user.
            return jsonify({'message': 'User deleted successfully'}), 200 # Or 204 No Content
        else:
            # This case should be caught by find_one above, but kept for safety
            return jsonify({'message': 'User not found'}), 404

    except ObjectId.InvalidId:
        return jsonify({'message': 'Invalid User ID format'}), 400
    except Exception as e:
        current_app.logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'message': 'Error deleting user'}), 500

# --- COMBINED User Update Route ---
@admin_bp.route('/users/<string:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Updates a user's details (username, email, isAdmin)."""
    db = get_db()
    admin_user_id = g.current_user.get('id')
    data = request.get_json()

    if not user_id:
        return jsonify({'message': 'User ID is required'}), 400
    if not data:
         return jsonify({'message': 'Request body is required'}), 400

    try:
        user_id_obj = ObjectId(user_id)
    except ObjectId.InvalidId:
        return jsonify({'message': 'Invalid User ID format'}), 400

    # Fields to potentially update
    update_fields = {}
    validation_errors = []

    if 'username' in data:
        username = data['username']
        if not isinstance(username, str) or len(username.strip()) < 3:
            validation_errors.append('Username must be a string of at least 3 characters.')
        else:
            update_fields['username'] = username.strip()

    if 'email' in data:
        email = data['email']
        # Basic email format check (can be improved with regex)
        if not isinstance(email, str) or '@' not in email or '.' not in email.split('@')[-1]:
            validation_errors.append('Invalid email format provided.')
        else:
            update_fields['email'] = email.lower().strip() # Store lowercase email

    if 'isAdmin' in data:
        is_admin = data['isAdmin']
        if not isinstance(is_admin, bool):
             validation_errors.append('Invalid isAdmin value (must be true or false).')
        else:
            # Prevent admin from removing their own admin status via this route
            if user_id == admin_user_id and not is_admin:
                return jsonify({'message': 'Admin cannot remove their own admin role via this update'}), 403
            update_fields['isAdmin'] = is_admin

    if validation_errors:
        return jsonify({'message': 'Validation failed', 'errors': validation_errors}), 400

    if not update_fields:
        return jsonify({'message': 'No valid fields provided for update'}), 400

    # Check for conflicts (username/email already taken by ANOTHER user)
    conflict_query = {'_id': {'$ne': user_id_obj}} # Exclude the current user
    conflict_or_conditions = []
    if 'username' in update_fields:
        conflict_or_conditions.append({'username': update_fields['username']})
    if 'email' in update_fields:
        conflict_or_conditions.append({'email': update_fields['email']})

    if conflict_or_conditions:
        conflict_query['$or'] = conflict_or_conditions
        try:
            existing_user = db.users.find_one(conflict_query)
            if existing_user:
                field = 'username' if existing_user.get('username') == update_fields.get('username') else 'email'
                return jsonify({'message': f'{field.capitalize()} "{data[field]}" is already taken by another user.'}), 409
        except Exception as e:
             current_app.logger.error(f"Database error checking user conflict: {str(e)}")
             return jsonify({'message': 'Error checking for existing user conflicts'}), 500


    # Perform the update
    try:
        result = db.users.update_one(
            {'_id': user_id_obj},
            {'$set': update_fields}
        )

        if result.matched_count == 0:
            return jsonify({'message': 'User not found'}), 404
        elif result.modified_count >= 1: # Could modify multiple fields
            updated_keys = list(update_fields.keys())
            current_app.logger.info(f"Admin {admin_user_id} updated user {user_id} fields: {updated_keys}")
            return jsonify({'message': 'User updated successfully'}), 200
        else:
            # Matched but not modified (likely data submitted was same as existing)
            return jsonify({'message': 'No changes detected in submitted data'}), 200

    except Exception as e:
        current_app.logger.error(f"Error updating user {user_id}: {str(e)}")
        return jsonify({'message': 'Error updating user'}), 500


# === Order Management Routes ===

@admin_bp.route('/orders', methods=['GET'])
@admin_required
def get_all_orders():
    """Fetches all orders with user details, sorted by date."""
    db = get_db()
    try:
        # Use aggregation pipeline to join orders with user data
        pipeline = [
            { '$sort': {'orderDate': -1} }, # Sort orders by date descending first
            {
                '$lookup': {
                    'from': 'users', # The name of the users collection
                    'localField': 'userId',
                    'foreignField': '_id',
                    'as': 'userDetails'
                }
            },
            {
                '$unwind': { # Deconstruct the userDetails array
                    'path': '$userDetails',
                    'preserveNullAndEmptyArrays': True # Keep orders even if user is deleted
                }
            },
            {
                '$project': { # Select and reshape the output
                    '_id': 1, # Keep original order ID for later renaming
                    'orderDate': 1,
                    'totalAmount': 1,
                    'paymentMethod': 1,
                    'paymentStatus': 1,
                    'shippingAddress': 1,
                    'items': 1,
                    'razorpay': 1,
                    'estimatedDeliveryDate': 1, # Include estimated delivery date
                    'user': { # Create a nested user object
                       # Safely access nested fields
                       'id': '$userDetails._id',
                       'username': '$userDetails.username',
                       'email': '$userDetails.email'
                       # Exclude password_hash implicitly
                    }
                }
            }
        ]

        orders_cursor = db.orders.aggregate(pipeline)
        orders_list = []
        for order in orders_cursor:
            order['id'] = str(order.pop('_id')) # Rename _id to id
            # Ensure user id is string if user exists
            if 'user' in order and order['user'] and order['user'].get('id'):
                order['user']['id'] = str(order['user']['id'])
            else:
                # Handle cases where user might be missing (due to preserveNullAndEmptyArrays or missing user fields)
                order['user'] = order.get('user', { 'id': None, 'username': 'N/A', 'email': 'N/A' }) # Provide default user structure

            # Format dates
            if 'orderDate' in order and isinstance(order['orderDate'], datetime.datetime):
                order['orderDate'] = order['orderDate'].isoformat()
            if 'estimatedDeliveryDate' in order and order['estimatedDeliveryDate'] and isinstance(order['estimatedDeliveryDate'], datetime.datetime):
                 order['estimatedDeliveryDate'] = order['estimatedDeliveryDate'].isoformat()

            orders_list.append(order)

        return jsonify(orders_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all orders: {str(e)}")
        return jsonify({'message': 'Could not retrieve orders', 'error': str(e)}), 500


@admin_bp.route('/orders/<string:order_id>', methods=['GET'])
@admin_required
def get_order_details(order_id):
    """Fetches details for a specific order (accessible by admin)."""
    db = get_db()
    try:
        order_id_obj = ObjectId(order_id)

        # Use aggregation similar to get_all_orders but match the specific ID
        pipeline = [
            { '$match': {'_id': order_id_obj} },
             {
                '$lookup': {
                    'from': 'users',
                    'localField': 'userId',
                    'foreignField': '_id',
                    'as': 'userDetails'
                }
            },
            { '$unwind': {'path': '$userDetails', 'preserveNullAndEmptyArrays': True} },
            {
                '$project': { # Select and reshape the output (same as get_all_orders)
                    '_id': 1, 'orderDate': 1, 'totalAmount': 1, 'paymentMethod': 1,
                    'paymentStatus': 1, 'shippingAddress': 1, 'items': 1, 'razorpay': 1,
                    'estimatedDeliveryDate': 1,
                    'user': {
                       'id': '$userDetails._id', 'username': '$userDetails.username',
                       'email': '$userDetails.email'
                    }
                }
            }
        ]

        order_list = list(db.orders.aggregate(pipeline)) # Execute pipeline

        if not order_list:
            return jsonify({'message': 'Order not found'}), 404

        order = order_list[0] # Get the single result

        # Format fields for response
        order['id'] = str(order.pop('_id'))
        if 'user' in order and order['user'] and order['user'].get('id'):
             order['user']['id'] = str(order['user']['id'])
        else:
             order['user'] = order.get('user', { 'id': None, 'username': 'N/A', 'email': 'N/A' })
        if 'orderDate' in order and isinstance(order['orderDate'], datetime.datetime):
            order['orderDate'] = order['orderDate'].isoformat()
        if 'estimatedDeliveryDate' in order and order['estimatedDeliveryDate'] and isinstance(order['estimatedDeliveryDate'], datetime.datetime):
             order['estimatedDeliveryDate'] = order['estimatedDeliveryDate'].isoformat()

        return jsonify(order), 200

    except ObjectId.InvalidId:
        return jsonify({'message': 'Invalid Order ID format'}), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching details for order {order_id}: {str(e)}")
        return jsonify({'message': 'Could not retrieve order details', 'error': str(e)}), 500


@admin_bp.route('/orders/<string:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    """Updates the status of a specific order."""
    db = get_db()
    admin_user_id = g.current_user.get('id')
    data = request.get_json()

    if not order_id:
        return jsonify({'message': 'Order ID is required'}), 400
    if not data or 'status' not in data:
        return jsonify({'message': 'Missing status field in request body'}), 400

    new_status = data['status'].lower() # Convert to lowercase for consistent check

    # Validate the status against allowed values
    if new_status not in ALLOWED_ORDER_STATUSES:
        return jsonify({'message': f'Invalid status value. Allowed statuses are: {", ".join(ALLOWED_ORDER_STATUSES)}'}), 400

    try:
        order_id_obj = ObjectId(order_id)
        result = db.orders.update_one(
            {'_id': order_id_obj},
            # Using paymentStatus field name for now, rename later if desired
            {'$set': {'paymentStatus': new_status}}
        )

        if result.matched_count == 0:
            return jsonify({'message': 'Order not found'}), 404
        elif result.modified_count == 1:
            current_app.logger.info(f"Admin {admin_user_id} updated order {order_id} status to {new_status}")
            # Optionally: Trigger notification to user about status change
            return jsonify({'message': 'Order status updated successfully'}), 200
        else:
             # Matched but not modified (status was already the target value)
            return jsonify({'message': 'Order status was already set to the requested value'}), 200

    except ObjectId.InvalidId:
        return jsonify({'message': 'Invalid Order ID format'}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating status for order {order_id}: {str(e)}")
        return jsonify({'message': 'Error updating order status'}), 500