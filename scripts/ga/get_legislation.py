#!/usr/bin/env python
import urlparse
from lxml.html import parse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyutils.legislation import (LegislationScraper, Bill, Vote, Legislator,
                                 NoDataForYear)

def ancestor_table(elm):
    if elm is None:
        return page
    ret = elm.getparent()
    while ret and ret.tag != 'table' and ret.tag != 'html':
        ret = ret.getparent()
    return ret

def table_index(parent, elm):
    tables = parent.cssselect('table')
    for i in xrange(len(tables)):
        tab = tables[i]
        if tab == elm:
            return i
    return None

class GALegislationScraper(LegislationScraper):
    """
    The GA files are compiled every two years.  They are in different formats
    between them, unfortunately, although it seems to coalesce around 2004.

    There are both bills and resolutions, each are included in this parser.

    The main search: http://www.legis.ga.gov/search.php
    It sucks, as you are forced to search for specific words.

    So, instead you can go directly a summary of each bill:

    From 1995 to 2000:
    http://www.legis.ga.gov/legis/<session>/leg/sum/<chamber><type><number>.htm
    e.g. http://www.legis.ga.gov/legis/1997_98/leg/sum/hb1.htm

    From 2001 on:
    http://www.legis.ga.gov/legis/<session>/sum/<chamber><type><number>.htm
    e.g. http://www.legis.ga.gov/legis/2009_10/sum/hb1.htm

    Where:
        <session> is the years of the session
        <chamber> is "h" or "s" for house and senate
        <type> is "b" or "r" for bill and resolution
        <number> is the number of the resoltion or bill

    Each session needs its own parser, so we will do it manually...
    """

    state = 'ga'

    def scrape_bills(self, chamber, year):
        year = int(year)

        if (year < 1995):
            raise NoDataForYear(year)
        if (year % 2 == 0):
            raise NoDataForYear(year)

        if year <= 2000:
            base = "http://www.legis.ga.gov/legis/%s/leg/sum/%s%s%d.htm"
        else:
            base = "http://www.legis.ga.gov/legis/%s/sum/%s%s%d.htm"

        session = "%s_%s" % (year, str(year + 1)[2:])

        chamberName = chamber
        chamber = {'lower': 'h', 'upper': 's'}[chamber]

        try:
            scraper = getattr(self, 'scrape%s' % year)
        except AttributeError:
            raise NoDataForYear(year)

        for type in ('b', 'r'):
            number = 1
            while True:
                url = base % (session, chamber, type, number)
                try:
                    scraper(url, year, chamberName, session, number)
                except IOError:
                    break
                number += 1

    def scrape1995(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/1995_96/leg/sum/sb1.htm"
        page = parse(url).getroot()

        # Bill
        name = page.cssselect('h3 br')[0].tail.split('-', 1)[1].strip()
        bill = Bill(session, chamberName, number, name)

        # Versions
        bill.add_version('Current', url.replace('/sum/', '/fulltext/'))

        # Sponsorships
        rows = page.cssselect('center table tr')
        for row in rows:
            if row.text_content().strip() == 'Sponsor and CoSponsors':
                continue
            if row.text_content().strip() == 'Links / Committees / Status':
                break
            for a in row.cssselect('a'):
                bill.add_sponsor('', a.text_content().strip())

        # Actions
        # The actions are in a pre table that looks like:
        """    SENATE                         HOUSE
               -------------------------------------
             1/13/95   Read 1st time          2/6/95
             1/31/95   Favorably Reported
             2/1/95    Read 2nd Time          2/7/95
             2/3/95    Read 3rd Time
             2/3/95    Passed/Adopted                   """

        actions = page.cssselect('pre')[0].text_content().split('\n')
        actions = actions[2:]
        for action in actions:
            senate_date = action[:22].strip()
            action_text = action[23:46].strip()
            house_date = action[46:].strip()

            if '/' not in senate_date and '/' not in house_date:
                continue

            if senate_date:
                bill.add_action('upper', action_text, senate_date)

            if house_date:
                bill.add_action('lower', action_text, house_date)

        self.add_bill(bill)

    def scrape1997(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/1997_98/leg/sum/sb1.htm"
        page = parse(url).getroot()

        # Grab the interesting tables on the page.
        tables = []
        for table in page.cssselect('center table'):
            if table.get('border') == '5':
                tables.append(table)

        # Bill
        name = page.cssselect('tr > td > font > b')[0].text_content().split(
            '-', 1)[1]
        bill = Bill(session, chamberName, number, name)

        # Versions
        bill.add_version('Current', url.replace('/sum/', '/fulltext/'))

        # Sponsorships
        for a in tables[0].cssselect('a'):
            if a.text_content().strip() == 'Current':
                break
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes(url, page, chamberName, bill)

        # Actions
        for row in tables[1].cssselect('tr'):
            senate_date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            house_date = row[2].text_content().strip()
            if '/' not in senate_date and '/' not in house_date:
                continue
            if senate_date:
                bill.add_action('upper', action_text, senate_date)
            if house_date:
                bill.add_action('lower', action_text, house_date)

        self.add_bill(bill)

    def scrape1999(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/1999_00/leg/sum/sb1.htm"
        page = parse(url).getroot()

        # Grab the interesting tables on the page.
        tables = page.cssselect('table')

        # Bill
        name = tables[1].cssselect('a')[0].text_content().split('-', 1)[1]
        bill = Bill(session, chamberName, number, name)

        # Versions
        bill.add_version('Current', url.replace('/sum/', '/fulltext/'))

        # Sponsorships
        for a in tables[2].cssselect('a'):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes_1999(url, page, chamberName, bill)

        # Actions
        for row in tables[-1].cssselect('tr'):
            senate_date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            house_date = row[2].text_content().strip()
            if '/' not in senate_date and '/' not in house_date:
                continue
            if senate_date:
                bill.add_action('upper', action_text, senate_date)
            if house_date:
                bill.add_action('lower', action_text, house_date)

        self.add_bill(bill)

    def scrape2001(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/2001_02/sum/sb1.htm"
        page = parse(url).getroot()

        # Grab the interesting tables on the page.
        tables = page.cssselect('table center table')

        # Bill
        name = tables[0].text_content().split('-', 1)[1]
        bill = Bill(session, chamberName, number, name)

        # Sponsorships
        for a in tables[1].cssselect('a'):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes_2001_2004(url, page, chamberName, bill)

        # Actions
        center = page.cssselect('table center')[-1]

        for row in center.cssselect('table table')[0].cssselect('tr')[2:]:
            date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            if '/' not in date:
                continue
            if action_text.startswith('Senate'):
                action_text = action_text.split(' ', 1)[1].strip()
                bill.add_action('upper', action_text, date)
            elif action_text.startswith('House'):
                action_text = action_text.split(' ', 1)[1].strip()
                bill.add_action('lower', action_text, date)

        # Versions
        for row in center.cssselect('table table')[1].cssselect('a'):
            bill.add_version(a.text_content(),
                             urlparse.urljoin(url, a.get('href')))

        self.add_bill(bill)

#    def parse_votes_2001(self, url, page, chamberName, bill):
#        vote_links = filter(lambda a: a.get('href') and a.get('href').find('../votes/') == 0, page.cssselect('a'))
#        for a in vote_links:
#            vote_url = urlparse.urljoin(url, a.get('href'))
#            print "vote_url: %s" % vote_url
#            vote_page = parse(vote_url).getroot()
#            date_table = vote_page.cssselect('table table')[5]
#            motion = date_table.cssselect('td')[3].text_content()
#            date = date_table.cssselect('td font font')[0].text + ' ' + \
#                date_table.cssselect('td font font')[1].text
#            counts_line = vote_page.cssselect('table table')[6].text_content().split()
#            yeses = int(counts_line[2].strip('0') or 0)
#            noes = int(counts_line[5].strip('0') or 0)
#            other = int(counts_line[8].strip('0') or 0) + int(counts_line[11].strip('0') or 0)
#            vote_obj = Vote(chamberName, date, motion, yeses > noes, yeses, noes, other)
#            vote_vals = vote_page.cssselect('table table')[7].cssselect('tr th')
#            vote_reps = vote_page.cssselect('table table')[7].cssselect('tr td')
#            for i in xrange(len(vote_vals)):
#                rep = vote_reps[i].text_content().strip()
#                val = vote_vals[i].text_content().strip()
#                if val == 'Y':
#                    vote_obj.yes(rep)
#                elif val == 'N':
#                    vote_obj.no(rep)
#                else:
#                    vote_obj.other(rep)
#            bill.add_vote(vote_obj)

    def parse_vote(self, vote_url, chamberName):
        page = parse(vote_url).getroot()
        summary_table = filter(lambda tab: tab.text_content().find('Yeas') == 0, page.cssselect('table'))[0]
        vote_table = ancestor_table(summary_table)
        ind = table_index(vote_table, summary_table)
        vote_tally_table = vote_table.cssselect('table')[ind+1]
        date_table = vote_table.cssselect('table')[ind-1]
        counts_line = summary_table.text_content().strip().split()
        yeses = int(counts_line[2].strip('0') or 0)
        noes = int(counts_line[5].strip('0') or 0)
        other = int(counts_line[8].strip('0') or 0) + int(counts_line[11].strip('0') or 0)
        
        tally_counts = filter(lambda p: p!='', map(str.strip, vote_tally_table.text_content().strip().split('\n')))

        if len(tally_counts[0]) > 1:
            tally_counts = map(lambda t: (t[:1], t[1:]), tally_counts)
        else:
            tc = []
            for i in xrange(0, len(tally_counts), 2):
                tc.append((tally_counts[i], tally_counts[i+1]))
            tally_counts = tc
            
        date_line = date_table.text_content().strip().split('\n')
        date = ' '.join(date_line[0:2])
        motion = date_line[-1]
        vote = Vote(chamberName, date, motion, yeses > noes, yeses, noes, other)
        print "tally_counts: %s" % tally_counts
        for tc in tally_counts:
            val = tc[0]
            rep = tc[1]
            if val == 'Y':
                vote.yes(rep)
            elif val == 'N':
                vote.no(rep)
            else:
                vote.other(rep)
        return vote

#    def parse_vote_old(self, vote_url, chamberName):
#        vote_page = parse(vote_url).getroot()
#        summary_table = filter(lambda tab: tab.text_content().find('Yeas') == 0, page.cssselect('table'))[0]
#        vote_table = self.ancestor_table(summary_table)
#        vote_tally_table = self.next_table(vote_table, summary_table)
#        summary = vote_page.cssselect('center table')[1].cssselect('tr')[0]
#        date = (summary.cssselect('td')[0].text + ' ' + summary.cssselect('td')[1].text).strip()
#        counts_line = vote_page.cssselect('center table')[2].cssselect('tr')[0].text_content().split()
#        print counts_line
#        yeses = int(counts_line[2].strip('0') or 0)
#        noes = int(counts_line[5].strip('0') or 0)
#        other = int(counts_line[8].strip('0') or 0) + int(counts_line[11].strip('0') or 0)
#        vote_obj = Vote(chamberName, date, '', yeses > noes, yeses, noes, other)
#        for vote in vote_page.cssselect('center table')[3].cssselect('tr tr'):
#            if len(vote) < 3:
#                continue
#            val = vote[1].text
#            rep = vote[2].text
#            if val == 'Y':
#                vote_obj.yes(rep)
#            elif val == 'N':
#                vote_obj.no(rep)
#            else:
#                vote_obj.other(rep)
#        return vote_obj

    def parse_votes_2001_2004(self, url, page, chamberName, bill):
        vote_links = filter(lambda a: a.get('href') and a.get('href').find('../votes/') == 0, page.cssselect('a'))
        for a in vote_links:
            vote_url = urlparse.urljoin(url, a.get('href'))
            bill.add_vote(self.parse_vote(vote_url, chamberName))
        
    def parse_votes(self, url, page, chamberName, bill):
        # Votes
        for a in page.cssselect("#votes a"):
            vote_url = urlparse.urljoin(url, a.get('href'))
            vote_page = parse(vote_url).getroot()
            date = vote_page.cssselect('#date')[0].text
            yeses = int(vote_page.cssselect('#yea')[0].text)
            noes = int(vote_page.cssselect('#nay')[0].text)
            other = sum(map(lambda s: int(s.text), vote_page.cssselect('#not-voting')))
            vote_obj = Vote(chamberName, date, '', yeses > noes, yeses, noes, other)
            for vote in vote_page.cssselect('ul.roll-call li'):
                rep = vote.text_content().strip()
                val = vote[0].text
                if val == 'Y':
                    vote_obj.yes(rep)
                elif val == 'N':
                    vote_obj.no(rep)
                else:
                    vote_obj.other(rep)
            bill.add_vote(vote_obj)        

    def scrape2003(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/2003_04/sum/sb1.htm"
        page = parse(url).getroot()

        # Grab the interesting tables on the page.
        tables = page.cssselect('center table')

        # Bill
        name = tables[0].text_content().split('-', 1)[1]
        bill = Bill(session, chamberName, number, name)

        # Sponsorships
        for a in tables[1].cssselect('a'):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes_2001_2004(url, page, chamberName, bill)

        # Actions
        center = page.cssselect('center table center')[0]

        for row in center.cssselect('table')[-2].cssselect('tr')[2:]:
            date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            if '/' not in date:
                continue
            if action_text.startswith('Senate'):
                bill.add_action('upper', action_text, date)
            elif action_text.startswith('House'):
                bill.add_action('lower', action_text, date)

        # Versions
        for row in center.cssselect('table')[-1].cssselect('a'):
            bill.add_version(a.text_content(),
                             urlparse.urljoin(url, a.get('href')))

        self.add_bill(bill)

    def scrape2005(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/2005_06/sum/sb1.htm"
        page = parse(url).getroot()

        # Bill
        name = page.cssselect('#legislation h1')[0].text_content().strip()
        bill = Bill(session, chamberName, number, name)

        # Sponsorships
        for a in page.cssselect("#sponsors a"):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes(url, page, chamberName, bill)

        # Actions
        for row in page.cssselect('#history tr')[1:]:
            date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            if '/' not in date:
                continue
            if action_text.startswith('Senate'):
                bill.add_action('upper', action_text, date)
            elif action_text.startswith('House'):
                bill.add_action('lower', action_text, date)

        # Versions
        for row in page.cssselect('#versions a'):
            bill.add_version(a.text_content(),
                             urlparse.urljoin(url, a.get('href')))

        self.add_bill(bill)

    def scrape2007(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/2007_08/sum/sb1.htm"
        page = parse(url).getroot()

        # Bill
        name = page.cssselect('#legislation h1')[0].text_content().strip()
        bill = Bill(session, chamberName, number, name)

        # Sponsorships
        for a in page.cssselect("#sponsors a"):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes(url, page, chamberName, bill)

        # Actions
        for row in page.cssselect('#history tr')[1:]:
            date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()
            if '/' not in date:
                continue
            if action_text.startswith('Senate'):
                bill.add_action('upper', action_text, date)
            elif action_text.startswith('House'):
                bill.add_action('lower', action_text, date)

        # Versions
        for row in page.cssselect('#versions a'):
            bill.add_version(a.text_content(),
                             urlparse.urljoin(url, a.get('href')))

        self.add_bill(bill)

    
            
    def scrape2009(self, url, year, chamberName, session, number):
        "e.g. http://www.legis.ga.gov/legis/2009_10/sum/sb1.htm"
        page = parse(url).getroot()

        # Bill
        try:
            name = page.cssselect('#legislation h1')[0].text_content().strip()
        except:
            name = "Unknown"
        bill = Bill(session, chamberName, number, name)

        # Sponsorships
        for a in page.cssselect("#sponsors a"):
            bill.add_sponsor('', a.text_content().strip())

        self.parse_votes(url, page, chamberName, bill)
            

        # Actions
        for row in page.cssselect('#history tr')[1:]:
            date = row[0].text_content().strip()
            action_text = row[1].text_content().strip()

            if '/' not in date:
                continue

            if action_text.startswith('Senate'):
                bill.add_action('upper', action_text, date)
            elif action_text.startswith('House'):
                bill.add_action('lower', action_text, date)

        # Versions
        for row in page.cssselect('#versions a'):
            bill.add_version(a.text_content(),
                             urlparse.urljoin(url, a.get('href')))

        self.add_bill(bill)

if __name__ == '__main__':
    GALegislationScraper.run()
