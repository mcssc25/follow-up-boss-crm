from django.core.management.base import BaseCommand

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign, CampaignStep


# ── Kelly Davis HTML Signature ──────────────────────────────────────────────
KELLY_SIGNATURE = """<table cellpadding="0" cellspacing="0" style="font-family: Arial, Helvetica, sans-serif; margin-top: 24px; border-top: 2px solid #2b7a78; padding-top: 16px;">
  <tr>
    <td style="padding-right: 16px; vertical-align: top;">
      <strong style="font-size: 16px; color: #1a1a2e;">Kelly Davis</strong><br/>
      <span style="font-size: 13px; color: #555;">Realtor&reg; &middot; Big Beach AL</span><br/>
      <span style="font-size: 13px; color: #555;">Gulf Shores &amp; Orange Beach, Alabama</span><br/>
      <a href="mailto:kelly@bigbeachal.com" style="font-size: 13px; color: #2b7a78; text-decoration: none;">kelly@bigbeachal.com</a>
    </td>
  </tr>
  <tr>
    <td style="padding-top: 10px;">
      <a href="https://www.instagram.com/diy.davis/" style="text-decoration: none; margin-right: 8px;" title="Instagram">
        <img src="https://cdn-icons-png.flaticon.com/24/174/174855.png" alt="Instagram" width="22" height="22" style="vertical-align: middle; border: 0;" />
      </a>
      <a href="https://www.facebook.com/kelly.goodworth.davis" style="text-decoration: none; margin-right: 8px;" title="Facebook">
        <img src="https://cdn-icons-png.flaticon.com/24/733/733547.png" alt="Facebook" width="22" height="22" style="vertical-align: middle; border: 0;" />
      </a>
      <a href="https://www.youtube.com/@GulfShoresAlabamaRealEstate" style="text-decoration: none;" title="YouTube">
        <img src="https://cdn-icons-png.flaticon.com/24/1384/1384060.png" alt="YouTube" width="22" height="22" style="vertical-align: middle; border: 0;" />
      </a>
    </td>
  </tr>
</table>"""

PDF_URL = "https://crm.bigbeachal.com/media/big_beach_guide.pdf"

# ── 12-Email Nurture Sequence (from updated docx) ────────────────────────
EMAILS = [
    {
        "order": 1,
        "delay_days": 2,
        "subject": "Discover your perfect Gulf Shores Beach Property",
        "body": f"""<p>Hey {{{{first_name}}}},</p>

<p>I know that making the decision to purchase a second home at the beach can be both EXCITING and a little OVERWHELMING.</p>

<p>How will you know which area in Gulf Shores or Orange Beach makes the most sense as an investment that your family will also love to use?</p>

<p>Which amenities are must-haves for your family vacations vs. nice-to-have?</p>

<p>And how do you find a place that could maybe even become a retirement retreat when timing is right?</p>

<p><strong>We don\u2019t want you to feel lost.</strong></p>

<p>This is already a big decision\u2014taking your wealth and turning it into a tangible lifestyle asset instead of just watching numbers on a bank statement\u2014so why make it more stressful than it has to be?</p>

<p>That\u2019s why we created <strong><em>The Big Beach Method</em></strong>. It\u2019s a clear, simple set of steps designed to help your family find the perfect vacation home as easily as possible.</p>

<p><a href="{PDF_URL}">Click here to download The Big Beach Method Guide (PDF)</a></p>

<p>There\u2019s no opt-in or anything. The link takes you directly to the PDF.</p>

<p>Let me know if you have any questions or want to see how we can customize the Big Beach Method to your specific goals.</p>

<p>Have a great rest of your day!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 2,
        "delay_days": 2,
        "subject": "Have you discovered any favorite condos yet?",
        "body": f"""<p>Hey {{{{first_name}}}}!</p>

<p>Did you find \u201cthe one\u201d or do you need to keep hunting?</p>

<p>I want to help you find the legacy home that\u2019s right for your family\u2014a central hub where your older kids will actually <em>want</em> to hang out with you. A place you can vacation now, and eventually retire in later.</p>

<p>But to do that, I need to know what you\u2019re looking for! So\u2026 just fill out these quick questions and I\u2019ll be able to send you a custom list of homes with the beach access and space you\u2019ve been dreaming of. You\u2019ll be notified of new listings as SOON as they hit the market.</p>

<ul>
<li>Timeline for purchase (some buyers find their perfect home in a matter of weeks and some can take a year or even two years to find the right spot):</li>
<li>Condo or House?</li>
<li>ON the Beach? Gulf Views? Under 5 min walk to the beach?</li>
<li>Price range:</li>
<li>Have you been pre-approved?</li>
<li>Must have amenities? Private Pool? Community Pool? Grilling area?</li>
<li>Min. Bedrooms /or how many do you need to sleep? (room for the kids/guests?):</li>
<li>Min. Bathrooms:</li>
<li>Preferred Neighborhoods/Complexes:</li>
</ul>

<p>If you\u2019re not sure exactly what you\u2019re looking for yet, let\u2019s set up a call so we can start narrowing down the right area for you.</p>

<p>Looking forward to helping you search!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 3,
        "delay_days": 2,
        "subject": "The biggest myth about buying a second home...",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>Many people tell me they worry that managing a second home in Gulf Shores from out of state is a huge headache. But that\u2019s simply not true!</p>

<p>Some of our clients choose not to rent their properties out at all. They just let family stay on occasion. Others use property management companies. And some have us help them set up the systems to self-manage from afar (like we did before moving here).</p>

<p>My goal is to make sure you are making the best decisions for your finances and your family, and I know how often we can get into our own heads when making a big out-of-state investment!</p>

<p>I want to make things easier for you and give you the real, honest truth. So if you want to avoid real estate pitfalls and find an asset you can truly enjoy, let\u2019s chat about how the Big Beach Method handles the heavy lifting.</p>

<p>Let\u2019s connect!</p>

<p>Talk soon!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 4,
        "delay_days": 2,
        "subject": "From a Bank Statement to a Beach House \U0001f4c8",
        "body": f"""<p>Hey {{{{first_name}}}},</p>

<p>We have quite a successful and experienced team ready to help you!</p>

<p>There are no bad questions. Do you need someone to just listen to your situation and give honest guidance? That\u2019s what we\u2019re here for.</p>

<p>Dave is an experienced lender who has helped hundreds of second-home buyers. He\u2019s also a Realtor and Investor that has been through this process of buying a second home personally and alongside MANY clients. A wealth of knowledge and strong communication.</p>

<p>I am always posting and adding stories about new restaurants, what the beach looks like today and local activities. I hope you\u2019ll follow along!</p>

<p>Best,</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 5,
        "delay_days": 2,
        "subject": "How the [Last Name] Family created their Ultimate Hub",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>[Insert post here about a past client. Example: \u201cThe Smith family came to me because they noticed their older kids were getting busy, and family vacations were becoming harder to plan. They wanted an anchor\u2014a \u2018family hub\u2019 that the kids would always want to come back to. Using my Big Beach Method, we found them a gorgeous Gulf Shores property. Now they have a tangible asset they can see and enjoy, an amazing place to vacation, and eventually, a beautiful home to retire in\u2026\u201d]</p>

<p><a href="#">Click here to hear more about their experience using my Beachside Relocation Method</a></p>

<p>If you\u2019re ready to achieve results like this\u2014to create a space your family loves while making a smart investment\u2014then let\u2019s set up a quick session so I can learn more about your vision for a second home.</p>

<p>Shoot me a text at {{{{agent_phone}}}} and we\u2019ll get a time set up asap!</p>

<p>Talk soon!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 6,
        "delay_days": 3,
        "subject": "The Top 3 Vacation Home Neighborhoods in Gulf Shores",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>I wanted to share a quick video with you about the absolute best neighborhoods in Gulf Shores for finding a second home or lifestyle asset. If you want a place that\u2019s low-maintenance but offers incredible beach access and amenities, you need to see this!</p>

<p><strong>West Beach:</strong> Nestled between The Gulf and Little Lagoon. Low density condos and many single family homes and duplexes. Quieter beaches.</p>

<p><strong>East Beach:</strong> More condos and closer to restaurants.</p>

<p><strong>Orange Beach:</strong> Many high rise condos, newer properties and more restaurants nearby.</p>

<p><a href="#">Click here to check it out!</a></p>

<p>Let me know your thoughts in the comments (and don\u2019t forget to give my page a like if you want more helpful tips)!</p>

<p>Best,</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 7,
        "delay_days": 3,
        "subject": 'The "Looming Empty Nest"',
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>[Insert a written pain/problem post: \u201cYou see your kids getting older and starting their own lives, and you start to wonder: will our suburban house still be the \u2018home base\u2019 once they are out on their own? You don\u2019t want to be the house they visit only for holidays. You want a place that pulls the family together\u2014a place in Gulf Shores that they can\u2019t wait to visit with their own friends or future kids\u2026\u201d]</p>

<p><a href="#">Click here to watch the full video if applicable</a></p>

<p>If you\u2019re feeling this exact way, grab a copy of my free guide to see how we can turn that fear into an exciting new reality for your family. There is nothing like a beach house to keep the family firmly anchored together!</p>

<p>Talk soon!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 8,
        "delay_days": 3,
        "subject": "{{first_name}}",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>Are you still looking to invest in a beach home? Or have your plans changed?</p>

<p style="margin-bottom: 0;">- Kelly</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 9,
        "delay_days": 3,
        "subject": "Feel more prepared with my FREE Out-Of-State Buyer\u2019s Checklist",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>I know sometimes it can seem like buying a second home in a completely different state can be overwhelming. There are quite a few moving parts when purchasing a property that you won\u2019t live in full-time right away!</p>

<p>That\u2019s why I created a free checklist for you, so you know exactly what to do from start to finish. I want to make sure you feel prepared for everything. Investing your wealth into a lifestyle asset is a big deal! And if you\u2019ve never bought an out-of-state vacation property before, there can be a lot of unknowns.</p>

<p>I want to make sure you\u2019re informed at every step of the process.</p>

<p>It doesn\u2019t hurt to be more prepared! So I want to offer you a copy of my out-of-state second-home buyer\u2019s checklist.</p>

<p><a href="#">Click here to get your copy.</a> There\u2019s no opt-in. This will take you directly to the PDF.</p>

<p>Want to also get more information on steps you\u2019ll need to consider when preparing the home for your eventual retirement? Reply to this e-mail and I\u2019ll be happy to answer any questions!</p>

<p>Speak to you soon!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 10,
        "delay_days": 3,
        "subject": "The one thing that helped them feel ready to make the leap",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>Remember my clients from a couple of emails ago? Well, that wasn\u2019t the whole story\u2026</p>

<p>[Insert post here: Focus on a different aspect of the purchase, like how you helped them discover that owning a vacation home felt dramatically more fulfilling than just watching their 401k on a screen, or how taking the leap relieved their anxiety about having a place secured for retirement.]</p>

<p><a href="#">Click here to hear more about their experience working with me</a></p>

<p>If you\u2019re ready to achieve results like this and execute a seamless property transaction from out of state, then let\u2019s set up a quick strategy session.</p>

<p>Shoot me a text at {{{{agent_phone}}}} and we\u2019ll get a time set up asap!</p>

<p>Talk soon!</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 11,
        "delay_days": 3,
        "subject": "Taking off the mask\u2026.",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>Over the last month, I\u2019ve been delivering helpful information on how to find the perfect second home in Gulf Shores. But today I wanted to take off the mask and introduce you to who I am when I\u2019m not helping people buy and sell real estate.</p>

<p>This is a little snippet of Kelly, the wife/mom/friend, and small town beach-lover</p>

<p>[Insert a written personal story: Share your own experience of investing in property or why the beach lifestyle means so much to you and your family. Relate to their desire for a tangible legacy asset!]</p>

<p><a href="#">Click here to watch the related video if applicable</a></p>

<p>Thank you for letting me share my family\u2019s journey with you!</p>

<p style="margin-bottom: 0;">- Kelly</p>

{KELLY_SIGNATURE}""",
    },
    {
        "order": 12,
        "delay_days": 2,
        "subject": "Wanna be friends?",
        "body": f"""<p>Hi {{{{first_name}}}},</p>

<p>Did you know I post helpful content on my Instagram and Facebook pages regularly?</p>

<p>My goal is to help you become an educated home buyer, especially when you are looking to invest in a vacation home from afar. It\u2019s important to me that you get the most up-to-date and relevant information about the Gulf Shores lifestyle, local areas, and the real estate market.</p>

<p>It\u2019ll also give you a chance to get to know me better and see what I\u2019m all about! Feel free to give me a follow so you don\u2019t miss out on anything you need to know about making the beach transition.</p>

<p><a href="https://www.instagram.com/diy.davis/">Click here to follow me on Instagram.</a></p>
<p><a href="https://www.facebook.com/kelly.goodworth.davis">Click here to follow me on my Facebook page.</a></p>
<p><a href="https://www.youtube.com/@GulfShoresAlabamaRealEstate">Subscribe to our YouTube channel!</a></p>

<p>Hope to see you there!</p>

<p style="margin-bottom: 0;">- Kelly</p>

{KELLY_SIGNATURE}""",
    },
]


class Command(BaseCommand):
    help = "Load the 30-Day Big Beach Method email nurture campaign"

    def handle(self, *args, **options):
        team = Team.objects.first()
        if not team:
            self.stderr.write("No team found. Run setup_initial_data first.")
            return

        admin = User.objects.filter(is_superuser=True).first()

        campaign, created = Campaign.objects.get_or_create(
            name="30-Day Big Beach Method Nurture Sequence",
            team=team,
            defaults={
                "description": "12-email nurture sequence over 30 days. Guides leads from initial guide delivery through authority building, case studies, and personal connection. Emails include Kelly Davis signature and social links.",
                "created_by": admin,
                "is_active": True,
            },
        )

        if not created:
            campaign.steps.all().delete()
            self.stdout.write("Existing campaign found - replacing steps.")

        for email in EMAILS:
            CampaignStep.objects.create(
                campaign=campaign,
                order=email["order"],
                delay_days=email["delay_days"],
                delay_hours=0,
                subject=email["subject"],
                body=email["body"],
            )

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(EMAILS)} emails into '{campaign.name}'"
        ))
