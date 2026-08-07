// Category display rules, shared by server and client components.
//
// Deliberately its own module with no "use client" directive. These helpers
// are called from server components (the /categories page, the homepage) AND
// from client components (CategoryBrowser, MegaMenu). Exporting them from a
// "use client" file makes the server import throw at request time —
// "Attempted to call hasProducts() from the server but hasProducts is on the
// client" — which type-checking does not catch, because it is an RSC boundary
// rule rather than a type error.

// Structural, not `CategoryTreeItem`: these helpers only ever read one field,
// and requiring the full API type forced every caller to carry all nine.
// The Footer receives a deliberately narrow projection and could not call
// them at all. Generics keep the caller's own type on the way out.
type Countable = { total_product_count?: number };

/** Minimum products before a category is linked anywhere on the public site.
 *
 *  Categories below this are the "broken pages": a heading over an empty grid,
 *  which reads as a soft 404 to Google and a dead end to a buyer. They are
 *  already excluded from the sitemap and noindexed on their own page, so the
 *  navigation was the last thing still advertising them. Nothing is deleted —
 *  a category reappears automatically the moment a product is filed under it.
 *
 *  Raise this to 2 to also hide single-product categories. */
export const MIN_PRODUCTS_TO_DISPLAY = 1;

/** Products in this category and everything beneath it. */
export function categoryProductCount(category: Countable): number {
  return category.total_product_count ?? 0;
}

export function hasProducts(category: Countable): boolean {
  return categoryProductCount(category) >= MIN_PRODUCTS_TO_DISPLAY;
}

/** Sub-categories carry their own count, not a subtree total. */
export function childHasProducts(child: { product_count?: number }): boolean {
  return (child.product_count ?? 0) >= MIN_PRODUCTS_TO_DISPLAY;
}

export function stockedCategories<T extends Countable>(categories: T[]): T[] {
  return categories.filter(hasProducts);
}
