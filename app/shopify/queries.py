"""Fixed, read-only Admin GraphQL operations pinned to the supported API version."""

SHOP_QUERY = """
query AnalyzerShop {
  shop { id name myshopifyDomain currencyCode ianaTimezone }
  currentAppInstallation { accessScopes { handle } }
}
"""

ORDERS_QUERY = """
query AnalyzerOrders($after: String, $query: String!) {
  orders(first: 10, after: $after, query: $query, sortKey: UPDATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id createdAt updatedAt test cancelledAt displayFinancialStatus
      netPaymentSet { shopMoney { amount currencyCode } }
      totalRefundedSet { shopMoney { amount currencyCode } }
      customerJourneySummary {
        ready customerOrderIndex
        lastVisit { utmParameters { source medium campaign } }
      }
      lineItems(first: 10) {
        pageInfo { hasNextPage }
        nodes {
          quantity currentQuantity
          originalUnitPriceSet { shopMoney { amount currencyCode } }
          variant { id product { id title } }
        }
      }
    }
  }
}
"""
