from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/invoices/<invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """
    A mock endpoint that returns invoice details.
    In a real application, this would fetch data from a database.
    """
    # In a real scenario, you would look this up.
    # For this example, we'll just return some static data
    # based on the ID to show the request was successful.
    if invoice_id == "123":
        return jsonify({
            "invoice_id": invoice_id,
            "amount": "USD 1000",
            "status": "paid"
        })
    else:
        return jsonify({
            "invoice_id": invoice_id,
            "amount": "USD 500",
            "status": "pending"
        })

if __name__ == '__main__':
    # Running on 0.0.0.0 makes it accessible from other containers
    app.run(host='0.0.0.0', port=5000, debug=True)


