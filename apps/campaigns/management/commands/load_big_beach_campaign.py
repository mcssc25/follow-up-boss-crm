from django.core.management.base import BaseCommand

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign, CampaignStep


EMAILS = [
    {
        "order": 1,
        "delay_days": 2,
        "subject": "A free guide to help you discover your perfect Gulf Shores Beach Property",
        "body": """<p>Hey {{first_name}},</p>

<p>I know that making the decision to purchase a second home at the beach can be both exciting and a little overwhelming.</p>

<p>How will you know which area in Gulf Shores makes the most sense as an investment that your family will also love to use?</p>

<p>Which amenities are must-haves for your family vacations vs. nice to have?</p>

<p>And how do you find a place that could also work as a retirement when timing is right?</p>

<p>I don't want you to feel lost. This is already a big decision\u2014taking your wealth and turning it into a tangible lifestyle asset instead of just watching numbers on a bank statement\u2014so why make it more stressful than it has to be?</p>

<p>That's why I created my Big Beach Method. It's a clear, simple set of steps designed to help your family find the perfect vacation home as easily as possible.</p>

<p><a href="#">Click here to read the guide.</a></p>

<p>There's no opt-in or anything. The link takes you directly to the PDF.</p>

<p>But before you read the guide, please watch this quick video to understand how my Big Beach Method can help you easily navigate buying a second home.</p>

<p><a href="#">Click here to watch</a></p>

<p>Let me know if you have any questions or want to see how we can customize the Big Beach Method to your specific goals.</p>

<p>Have a great rest of your day!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 2,
        "delay_days": 2,
        "subject": "Have you found your Gulf Shores haven yet?",
        "body": """<p>Hey {{first_name}}!</p>

<p>Did you find "the one" or do you need to keep hunting?</p>

<p>I want to help you find the legacy home that's right for your family\u2014a central hub where your older kids will actually <em>want</em> to hang out with you. A place you can vacation now, and eventually retire in later.</p>

<p>But to do that, I need to know what you're looking for! So... just fill out these quick questions and I'll be able to send you a custom list of homes with the beach access and space you've been dreaming of. You'll be notified of new listings as SOON as they hit the market.</p>

<ul>
<li>Timeline for purchase:</li>
<li>Condo or House?</li>
<li>ON the Beach? Gulf Views? Under 5 min walk to the beach?</li>
<li>Price range:</li>
<li>Have you been pre-approved?</li>
<li>Must have amenities? Private Pool? Community Pool? Grilling area?</li>
<li>Min. Bedrooms /or how many do you need to sleep?</li>
<li>Min. Bathrooms:</li>
<li>Preferred Neighborhoods/Complexes:</li>
</ul>

<p>If you're not sure exactly what you're looking for yet, let me know and we can have a chat about that, too! The best beach homes sell quickly, regardless of market conditions. I want to make sure I get you priority access.</p>

<p>Looking forward to helping you search!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 3,
        "delay_days": 2,
        "subject": "The biggest myth about buying a second home...",
        "body": """<p>Hi {{first_name}},</p>

<p>[Insert a video or written post here about the "Myth" of managing a second home. For instance: "Many people tell me they worry that managing a second home in Gulf Shores from out of state is a huge headache. But that's simply not true! With the right team in place, owning a beach house can be a completely hands-off experience until you are ready to visit..."]</p>

<p><a href="#">Click here to watch the video</a></p>

<p>My goal is to make sure you are making the best decisions for your finances and your family, and I know how often we can get into our own heads when making a big out-of-state investment!</p>

<p>I want to make things easier for you and give you the real, honest truth. So if you want to avoid real estate pitfalls and find an asset you can truly enjoy, let's chat about how my Big Beach Method handles the heavy lifting.</p>

<p>Let's connect!</p>

<p>Talk soon!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 4,
        "delay_days": 2,
        "subject": "From a Bank Statement to a Beach House \U0001f4c8",
        "body": """<p>Hey {{first_name}},</p>

<p>Did you know that I post helpful content on my Instagram &amp; Facebook page regularly? My goal is to help you become an educated beach home buyer.</p>

<p>I did a post recently about turning your hard-earned wealth\u2014which might currently just be sitting as numbers on a bank statement or disappearing into high state property taxes\u2014into a tangible asset. A beautiful property you can touch, see, and experience with your family.</p>

<p>[Insert written post here about how a beach home in Gulf Shores is a smart financial investment that also doubles as your private sanctuary, keeping your money working for you while giving you a place to vacation.]</p>

<p><a href="#">Click here to watch the video</a></p>

<p>Want more helpful tips? <a href="#">Follow me on Instagram</a>! I'm constantly posting more info on there that can really help you decide where to invest in Gulf Shores. Whether it's finding the best areas for future retirement or the top local dining spots, it doesn't hurt to stay up to date!</p>

<p>Best,</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 5,
        "delay_days": 2,
        "subject": "How the [Last Name] Family created their Ultimate Hub",
        "body": """<p>Hi {{first_name}},</p>

<p>[Insert post here about a past client. Example: "The Smith family came to me because they noticed their older kids were getting busy, and family vacations were becoming harder to plan. They wanted an anchor\u2014a 'family hub' that the kids would always want to come back to. Using my Big Beach Method, we found them a gorgeous Gulf Shores property. Now they have a tangible asset they can see and enjoy, an amazing place to vacation, and eventually, a beautiful home to retire in..."]</p>

<p><a href="#">Click here to hear more about their experience using my Beachside Relocation Method</a></p>

<p>If you're ready to achieve results like this\u2014to create a space your family loves while making a smart investment\u2014then let's set up a quick session so I can learn more about your vision for a second home.</p>

<p>Shoot me a text at {{agent_phone}} and we'll get a time set up asap!</p>

<p>Talk soon!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 6,
        "delay_days": 3,
        "subject": "The Top 3 Vacation Home Neighborhoods in Gulf Shores",
        "body": """<p>Hi {{first_name}},</p>

<p>I wanted to share a quick video with you about the absolute best neighborhoods in Gulf Shores for finding a second home or lifestyle asset. If you want a place that's low-maintenance but offers incredible beach access and amenities, you need to see this!</p>

<p><strong>West Beach:</strong> Nestled between The Gulf and Little Lagoon. Low density condos and many single family homes and duplexes. Quieter beaches.</p>

<p><strong>East Beach:</strong> More condos and closer to restaurants</p>

<p><strong>Orange Beach:</strong> Many high rise condos, newer properties and more restaurants nearby.</p>

<p><a href="#">Click here to check it out!</a></p>

<p>Let me know your thoughts in the comments (and don't forget to give my page a like if you want more helpful tips)!</p>

<p>Best,</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 7,
        "delay_days": 3,
        "subject": 'The "Looming Empty Nest"',
        "body": """<p>Hi {{first_name}},</p>

<p>[Insert a written pain/problem post: "You see your kids getting older and starting their own lives, and you start to wonder: will our suburban house still be the 'home base' once they are out on their own? You don't want to be the house they visit only for holidays. You want a place that pulls the family together\u2014a place in Gulf Shores that they can't wait to visit with their own friends or future kids..."]</p>

<p><a href="#">Click here to watch the full video</a></p>

<p>If you're feeling this exact way, grab a copy of my free guide to see how we can turn that fear into an exciting new reality for your family. There is nothing like a beach house to keep the family firmly anchored together!</p>

<p>Talk soon!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 8,
        "delay_days": 3,
        "subject": "{{first_name}}",
        "body": """<p>Hi {{first_name}},</p>

<p>Are you still looking to invest in a beach home? Or have your plans changed?</p>

<p>- {{agent_name}}</p>""",
    },
    {
        "order": 9,
        "delay_days": 3,
        "subject": "Feel more prepared with my FREE Out-Of-State Buyer's Checklist",
        "body": """<p>Hi {{first_name}},</p>

<p>I know sometimes it can seem like buying a second home in a completely different state can be overwhelming. There are quite a few moving parts when purchasing a property that you won't live in full-time right away!</p>

<p>That's why I created a free checklist for you, so you know exactly what to do from start to finish. I want to make sure you feel prepared for everything. Investing your wealth into a lifestyle asset is a big deal! And if you've never bought an out-of-state vacation property before, there can be a lot of unknowns.</p>

<p>I want to make sure you're informed at every step of the process.</p>

<p>It doesn't hurt to be more prepared! So I want to offer you a copy of my out-of-state second-home buyer's checklist.</p>

<p><a href="#">Click here to get your copy.</a> There's no opt-in. This will take you directly to the PDF.</p>

<p>Want to also get more information on steps you'll need to consider when preparing the home for your eventual retirement? Reply to this e-mail and I'll be happy to answer any questions!</p>

<p>Speak to you soon!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 10,
        "delay_days": 3,
        "subject": "The one thing that helped them feel ready to make the leap",
        "body": """<p>Hi {{first_name}},</p>

<p>Remember my clients from a couple of emails ago? Well, that wasn't the whole story\u2026</p>

<p>[Insert post here: Focus on a different aspect of the purchase, like how you helped them discover that owning a vacation home felt dramatically more fulfilling than just watching their 401k on a screen, or how taking the leap relieved their anxiety about having a place secured for retirement.]</p>

<p><a href="#">Click here to hear more about their experience working with me</a></p>

<p>If you're ready to achieve results like this and execute a seamless property transaction from out of state, then let's set up a quick strategy session.</p>

<p>Shoot me a text at {{agent_phone}} and we'll get a time set up asap!</p>

<p>Talk soon!</p>

<p>{{agent_name}}</p>""",
    },
    {
        "order": 11,
        "delay_days": 3,
        "subject": "Taking off the mask\u2026.",
        "body": """<p>Hi {{first_name}},</p>

<p>Over the last month, I've been delivering helpful information on how to find the perfect second home in Gulf Shores. But today I wanted to take off the mask and introduce you to who I am when I'm not helping people buy and sell real estate.</p>

<p>This is a little snippet of Kelly, the wife/mom/friend, and small town beach-lover</p>

<p>[Insert a written personal story: Share your own experience of investing in property or why the beach lifestyle means so much to you and your family. Relate to their desire for a tangible legacy asset!]</p>

<p><a href="#">Click here to watch the related video</a></p>

<p>Thank you for letting me share my family's journey with you!</p>

<p>- {{agent_name}}</p>""",
    },
    {
        "order": 12,
        "delay_days": 2,
        "subject": "Wanna be friends?",
        "body": """<p>Hi {{first_name}},</p>

<p>Did you know I post helpful content on my Instagram and Facebook pages regularly?</p>

<p>My goal is to help you become an educated home buyer, especially when you are looking to invest in a vacation home from afar. It's important to me that you get the most up-to-date and relevant information about the Gulf Shores lifestyle, local areas, and the real estate market.</p>

<p>It'll also give you a chance to get to know me better and see what I'm all about! Feel free to give me a follow so you don't miss out on anything you need to know about making the beach transition.</p>

<p><a href="#">Click here to follow me on Instagram.</a></p>
<p><a href="#">Click here to follow me on my Facebook page.</a></p>

<p>Hope to see you there!</p>

<p>- {{agent_name}}</p>""",
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
                "description": "12-email nurture sequence over 30 days. Guides leads from initial guide delivery through authority building, case studies, and personal connection.",
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
