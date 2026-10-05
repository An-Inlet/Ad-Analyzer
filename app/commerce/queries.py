ORDERS = """
query InletMeasurementOrders($after: String, $query: String!) {
 orders(first: 10, after: $after, query: $query, sortKey: UPDATED_AT) {
  pageInfo { hasNextPage endCursor }
  nodes { id createdAt updatedAt test customer { id } }
 }
}
"""

AGREEMENTS = """
query InletAgreements($id: ID!, $after: String) {
 order(id: $id) { agreements(first: 1, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { id happenedAt sales(first: 50) {
   pageInfo { hasNextPage endCursor }
   nodes { id actionType lineType totalAmount { shopMoney { amount currencyCode } }
    totalTaxAmount { shopMoney { amount currencyCode } } }
  } }
 } }
}
"""

SALES = """
query InletAgreementSales($order: ID!, $agreementBefore: String, $after: String) {
 order(id: $order) { agreements(first: 1, after: $agreementBefore) { nodes {
  id sales(first: 50, after: $after) {
   pageInfo { hasNextPage endCursor }
   nodes { id actionType lineType totalAmount { shopMoney { amount currencyCode } }
    totalTaxAmount { shopMoney { amount currencyCode } } }
  }
 } } }
}
"""
