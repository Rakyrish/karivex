import Link from "next/link";

type CategoryNavItem = { name: string; slug: string };

export default function CategoryNav({ categories }: { categories: CategoryNavItem[] }) {
  if (categories.length === 0) return null;

  return (
    <div className="category-nav">
      <nav className="category-nav-inner" aria-label="Product categories">
        <Link href="/products" className="category-chip category-chip-all">
          All products
        </Link>
        {categories.map((c) => (
          <Link key={c.slug} href={`/categories/${c.slug}`} className="category-chip">
            {c.name}
          </Link>
        ))}
      </nav>
    </div>
  );
}
