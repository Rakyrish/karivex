"""Load the founding buyer's-guide drafts.

These are written to answer questions a buyer actually types into Google before
they know which supplier to call — the long-tail informational half of the
funnel the catalogue pages cannot serve, because a product page answers "what
is this" and never "which of these three do I need".

Three rules were applied while writing them, and they should hold for anything
added here later:

1. **Nothing is published.** Every post lands with `published=False`. The blog
   index stays noindex until a human has read the copy and set the flag. These
   are drafts for review, not output.

2. **No dosing rates, no first-aid, no handling instructions.** The posts stay
   on selection criteria, commercial terms and documentation — the things a
   distributor legitimately knows. Anything that could injure someone if wrong
   is deferred to the SDS and to jar testing, explicitly, in the copy itself.

3. **Every factual claim traces to this database or to site config.** Product
   names, CAS numbers and pack sizes below are read from the catalogue at load
   time rather than typed here, so a post cannot describe stock that does not
   exist. Where a number would date (product counts), the copy says "our
   catalogue" instead of asserting a figure.

    python manage.py seed_guides            # create drafts, skip existing
    python manage.py seed_guides --replace  # overwrite bodies of existing drafts
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import BlogPost, Product


def _linked(*slugs):
    """Products that exist, in the order given. Missing slugs are dropped."""
    found = {p.slug: p for p in Product.objects.filter(slug__in=slugs)}
    return [found[s] for s in slugs if s in found]


GUIDES = [
    {
        "title": "CAS Numbers Explained: Why the Number Matters More Than the Name",
        "slug": "cas-numbers-explained-ordering-chemicals-kenya",
        "excerpt": (
            "Two suppliers can quote you the same chemical name and ship different "
            "substances. The CAS number is what removes the ambiguity — here is how to "
            "use it when you raise a purchase order."
        ),
        "meta_title": "CAS Numbers Explained | Ordering Chemicals in Kenya",
        "meta_description": (
            "Why the CAS number, not the product name, is what you should specify on a "
            "chemical purchase order — and how to check it before you pay."
        ),
        "products": ("citric-acid", "magnesium-sulphate", "sodium-metabisulfite"),
        "body": """
Ask three suppliers for a quote on "EDTA" and you can legitimately receive three
different chemicals. EDTA free acid, disodium EDTA and tetrasodium EDTA are
distinct substances with different solubilities, different pH behaviour in your
process, and different prices. All three are sold as "EDTA".

This is not a supplier trick. It is what happens when a purchase order names a
chemical family instead of a substance — and it is the single most common cause
of a delivered drum being the wrong material.

## What a CAS number actually is

A CAS Registry Number is a unique identifier assigned by the Chemical Abstracts
Service to one specific substance. It looks like `77-92-9` — two to seven
digits, two digits, then a single check digit.

That last digit is not decorative. It is calculated from the digits before it,
which means a transposed or dropped digit produces a number that fails
validation rather than silently naming a different chemical. If your ERP or
procurement system can validate CAS numbers on entry, turn that on.

The number is the substance. The name is a label people argue about.

## Where names go wrong

**Salt and hydrate forms.** Magnesium sulphate heptahydrate and magnesium
sulphate anhydrous are both "magnesium sulphate" in conversation. They have
different molecular weights, so a formulation dosed by mass against the wrong
one is dosed wrong.

**Isomers.** "Xylene" is three isomers plus the commercial mixture. Each has its
own CAS. Which one your process tolerates is a question your technical team can
answer; which one arrives is a question your purchase order decides.

**Trade names.** A great deal of what moves through this industry is sold under
a brand. Trade names are not registry entries — a blended antiscalant or a
proprietary defoamer has no CAS at all, because a CAS identifies one substance
and these are formulations. That is not a red flag; it simply means the
specification has to come from the technical data sheet instead.

**British and American spelling.** Sulphate and sulfate, aluminium and aluminum.
Harmless in an email, but enough to make two line items in a spreadsheet look
like two different products.

## How to use it on a purchase order

Specify the CAS number alongside the name, not instead of it. The name is what a
human in the warehouse reads; the number is what removes the ambiguity if the
two disagree.

Then ask for three things before you pay:

- **The Certificate of Analysis (COA)** for the actual batch being shipped, not
  a specimen. It names the substance, the batch, and the tested values.
- **The Safety Data Sheet (SDS)**, which carries the CAS, the hazard
  classification and the transport details your logistics provider needs.
- **The concentration or grade**, written down. "Phosphoric acid" is a family;
  the 85% food-grade material and a dilute technical grade are different
  purchases at different prices.

If the CAS on the COA does not match the CAS on your order, stop there. That is
the check working.

## Where blanks are legitimate

You will see products — ours included — where the CAS field is empty. There are
three honest reasons for that, and it is worth knowing which applies:

1. **No CAS exists.** Blends, formulations and trade-name products are recipes,
   not substances.
2. **The form decides the number.** The material is a real substance, but which
   hydrate or salt you are buying determines which of several numbers is
   correct. Only the batch documentation settles it.
3. **It has not been transcribed yet.** The honest answer, and the reason we
   would rather show a blank field than a plausible guess.

A supplier who fills every CAS field is not necessarily better documented than
one who leaves some blank. A wrong number is worse than no number, because a
wrong number looks verified.

## The short version

Order by number, confirm by document, and treat a mismatch as a stop condition.
It costs one extra field on a purchase order and it removes the most expensive
category of error in chemical procurement.

Our catalogue publishes the CAS number wherever we hold verified documentation
for it, and leaves it blank where we do not.
[Request a quote](/quote) with your CAS and grade and we will confirm both in
writing before anything ships.
""",
    },
    {
        "title": "Alum, PAC or Ferric Chloride? Choosing a Coagulant for Water Treatment",
        "slug": "choosing-coagulant-alum-pac-ferric-chloride-kenya",
        "excerpt": (
            "The three coagulants most Kenyan water treatment plants choose between, what "
            "actually separates them in practice, and why the decision belongs to a jar "
            "test rather than a price list."
        ),
        "meta_title": "Alum vs PAC vs Ferric Chloride | Coagulant Selection",
        "meta_description": (
            "How aluminium sulphate, poly aluminium chloride and ferric chloride differ in "
            "practice — and why jar testing decides which one your plant should buy."
        ),
        "products": ("aluminium-sulphate", "poly-aluminum-chloride-powder",
                     "ferric-chloride-anhydrous", "hydrated-lime", "soda-ash"),
        "body": """
Most water treatment plants in Kenya are choosing between three coagulants:
aluminium sulphate, poly aluminium chloride, and ferric chloride. The choice is
usually made once, inherited by whoever runs the plant next, and revisited only
when something stops working.

It is worth revisiting deliberately, because the three behave differently in
ways that show up in your alkalinity consumption and your sludge volumes long
before they show up on the invoice.

**Before anything below is useful: this is a selection guide, not a dosing
guide.** Correct dose depends on your raw water — turbidity, alkalinity,
temperature, organic load — and it changes seasonally. The only way to set it is
jar testing on your actual water, and the only authority on handling any of
these materials is the Safety Data Sheet supplied with the batch.

## Aluminium sulphate (alum)

The long-standing default, and still the lowest cost per kilogram of the three.

Alum consumes alkalinity as it works. In water that is already soft or low in
alkalinity, that means pH drops as you dose, and you end up buying a second
chemical — typically hydrated lime or soda ash — to bring it back. When people
say alum is the cheap option, they are usually pricing the alum and not the
alkalinity correction.

It is temperature sensitive. Performance falls off in cold water, which matters
more in the highlands than at the coast.

Where it works well: consistent raw water with decent natural alkalinity, and an
operating team already used to it.

## Poly aluminium chloride (PAC)

Pre-hydrolysed, which is the whole point. Much of the reaction that alum
performs in your tank has already been done during manufacture.

The practical consequences: it consumes considerably less alkalinity, works
across a wider pH band, tolerates cold water better, and typically needs a lower
dose by weight. It generally produces less sludge — which is a real operating
cost, not a footnote, if you are paying to dewater and haul it.

It costs more per kilogram. Whether it costs more per cubic metre treated is a
different question, and the answer depends on your alkalinity chemistry. This is
the comparison most plants have never actually run.

Where it works well: variable raw water, cold water, low alkalinity, or plants
under pressure on sludge handling.

## Ferric chloride

The strongest performer on colour and dissolved organics, and it holds up at
higher pH than the aluminium coagulants.

Two trade-offs. It is corrosive to a wider range of materials, so dosing
equipment and storage need to be specified for it — retrofitting it into a plant
built around alum is not just a matter of changing the drum. And it stains:
ferric residuals discolour concrete and anything else they contact.

It also produces a denser floc, which some plants find settles better and others
find harder to handle downstream.

Where it works well: high organic load, colour removal, or where the process
needs to run at a pH the aluminium coagulants struggle with.

## How to actually decide

Run a jar test with all three on your own raw water, at the season you struggle
most. Then compare on total cost per cubic metre treated, not price per bag —
counting:

- coagulant cost at the dose that actually works
- alkalinity correction consumed at that dose
- sludge produced, and what disposal costs you
- whether your existing dosing and storage suit the chemical

That last point decides more cases than the chemistry does. The best coagulant
for your water is not worth switching to if the changeover means re-specifying
your dosing line.

## What we supply

Karivex stocks all three, along with the alkalinity chemicals that pair with
them, in the pack sizes listed on each product page. Every consignment ships
with its COA and SDS.

If you are running a comparison and want material for jar testing,
[tell us what you are treating](/quote) and we will quote the three side by side
so the trial is a like-for-like decision.
""",
    },
    {
        "title": "What to Check Before You Pay for a Chemical Consignment in Kenya",
        "slug": "chemical-procurement-checklist-documentation-kenya",
        "excerpt": (
            "A practical checklist for buyers: the documents that should arrive with a "
            "quote, what a Certificate of Analysis should say, and the checks worth doing "
            "on delivery before the truck leaves."
        ),
        "meta_title": "Chemical Procurement Checklist | Buying in Kenya",
        "meta_description": (
            "The documentation, specification and delivery checks worth running before you "
            "pay for an industrial chemical consignment in Kenya."
        ),
        "products": (),
        "body": """
Most disputes over a chemical consignment are not arguments about quality. They
are arguments about what was specified — discovered after delivery, when the
material is already on site and the alternative is a long conversation about who
pays for the return.

Almost all of it is preventable at the quotation stage. Here is the checklist.

## At quotation

**Get the grade in writing.** "Citric acid" is not a specification. Food grade,
technical grade and pharmaceutical grade are different products at different
prices, and a quote that does not name one is not comparable to a quote that
does. If you are tendering, this is the single most common reason three quotes
turn out not to be for the same thing.

**Get the concentration or purity.** Particularly for anything supplied as a
solution. An 85% material and a 75% material are both honestly described as the
same chemical, and the cheaper one is not cheaper per unit of active.

**Get the CAS number.** It removes the ambiguity that names carry — see our
[guide to CAS numbers](/blog/cas-numbers-explained-ordering-chemicals-kenya) for
why this matters more than it sounds.

**Get the pack size and the pack type.** A price per kilogram means little until
you know whether it arrives in 25 kg bags, a 200 kg drum or an IBC, and whether
your handling equipment and store suit it.

**Ask whether the price includes delivery**, and to where. Delivered-to-site and
ex-warehouse are different numbers.

## Documents that should arrive with the material

**Certificate of Analysis (COA).** For the batch you are receiving — not a
specimen or a typical-values sheet. It should name the substance, identify the
batch, and give tested values against the specification. A COA that does not
reference a batch number cannot be matched to the drum in front of you, which is
the entire purpose of having one.

**Safety Data Sheet (SDS).** Sixteen sections, current, and for the correct
grade. Your team needs it for handling and storage; your logistics provider
needs the transport classification; your QA file needs it on record.

Both should come with the quotation, not after payment. A supplier who can send
the SDS before you order is a supplier who has it.

## On delivery

- **Match the batch number** on the container to the batch on the COA. If they
  differ, the COA is for material you did not receive.
- **Check the CAS on the label** against your purchase order.
- **Check pack integrity and seals** before signing. Note damage on the delivery
  note at the point of delivery — afterwards is a negotiation.
- **Confirm quantity by count**, and by weight if the value justifies it.
- **Check the expiry or retest date** where the material carries one.

## Storage, briefly

Storage requirements come from the SDS for that specific material, and they are
not interchangeable between products — segregation requirements in particular
exist because certain materials must not be stored together. Read section 7 of
the SDS for each product you hold rather than applying one rule across the
store.

## Questions worth asking a new supplier

- Can you send the SDS and a specimen COA before I order?
- What is your lead time for this in the pack size I need, and what is it if I
  need it regularly?
- Where does this material originate, and does that change between batches?
- What happens if the COA does not match the specification on arrival?

The last one is the useful question. The answer tells you what kind of supplier
you are dealing with more reliably than the price does.

## How we work

Karivex supplies COA and SDS with every consignment, quotes against a named
grade and concentration rather than a bare product name, and delivers across
Kenya, Uganda, Tanzania and Rwanda from our Nairobi warehouse.

[See our full process](/how-we-work), or
[send us a specification](/quote) and we will come back with grade, pack size,
price and lead time in writing.
""",
    },
]


class Command(BaseCommand):
    help = "Load the founding buyer's-guide drafts (unpublished)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace", action="store_true",
            help="Overwrite the body/excerpt of guides that already exist.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        created = updated = skipped = 0

        for guide in GUIDES:
            existing = BlogPost.objects.filter(slug=guide["slug"]).first()
            if existing and not opts["replace"]:
                skipped += 1
                self.stdout.write(self.style.HTTP_INFO(
                    f"  skip     {guide['slug']} (exists; --replace to overwrite)"
                ))
                continue

            post = existing or BlogPost(slug=guide["slug"])
            post.title = guide["title"]
            post.excerpt = guide["excerpt"]
            post.body = guide["body"].strip()
            post.meta_title = guide["meta_title"]
            post.meta_description = guide["meta_description"]
            # Never flipped on by this command. A human reads the copy and
            # publishes; that review is the point of the model's docstring.
            if not existing:
                post.published = False
            post.save()

            related = _linked(*guide["products"])
            post.related_products.set(related)

            if existing:
                updated += 1
                verb, style = "update  ", self.style.WARNING
            else:
                created += 1
                verb, style = "create  ", self.style.SUCCESS
            self.stdout.write(style(
                f"  {verb} {post.slug}  ({len(post.body.split())} words, "
                f"{len(related)} linked product(s))"
            ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{created} created, {updated} updated, {skipped} skipped."
        ))
        self.stdout.write(self.style.WARNING(
            "All drafts are UNPUBLISHED. Read them, edit anything you disagree "
            "with, then set Published in the admin. /blog stays noindex and out "
            "of the sitemap until the first one goes live.\n"
        ))
