"""Builds the sample project: demo/sample.pdf, a fictional building, and demo/review.json, its review.

The drawing has deliberate mistakes. review.json is written by hand for it, pointing at the text on
the sheets, so the app can show a full report with no API key. The app labels it as a sample.
Run after changing the drawing: .venv/bin/python build_sample.py (needs pymupdf-fonts).
"""
import json
from pathlib import Path
import pymupdf
import pdf_tools
from rulebook import BY_ID, RULES

OUT = Path(__file__).parent / 'demo'
M = 26            # points per metre: 1:110 on an A3 sheet
X0, Y0 = 130, 215
INK, THIN, RED = (0.13, 0.13, 0.15), (0.45, 0.45, 0.5), (0.75, 0.1, 0.1)
FONT = pymupdf.Font('figo')


class Sheet:
    def __init__(self, doc, title, number):
        self.page = doc.new_page(width=1191, height=842)
        self.page.insert_font(fontname='figo', fontbuffer=FONT.buffer)
        self.shape = self.page.new_shape()
        self.frame(title, number)

    def text(self, x, y, value, size=8, colour=INK):
        self.page.insert_text((x, y), value, fontname='figo', fontsize=size, color=colour)

    def label(self, x, y, value, size=8):
        """Text at drawing coordinates, in metres."""
        self.text(X0 + x * M, Y0 + y * M, value, size)

    def line(self, a, b, width=0.5, colour=INK):
        self.shape.draw_line(a, b)
        self.shape.finish(width=width, color=colour)

    def wall(self, x0, y0, x1, y1, width=1.6):
        self.line((X0 + x0 * M, Y0 + y0 * M), (X0 + x1 * M, Y0 + y1 * M), width)

    def room(self, x0, y0, x1, y1, width=1.6):
        for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            self.wall(a, b, c, d, width)

    def door(self, x, y, size=0.9, up=False):
        """A door leaf and its swing, at a wall."""
        px, py = X0 + x * M, Y0 + y * M
        sign = -1 if up else 1
        self.line((px, py), (px, py + sign * size * M), 0.6, THIN)
        self.shape.draw_curve((px, py + sign * size * M), (px + size * M * 0.75, py + sign * size * M * 0.75), (px + size * M, py))
        self.shape.finish(width=0.4, color=THIN)

    def stair(self, x0, y0, x1, y1):
        self.room(x0, y0, x1, y1, 2.4)
        steps = 12
        for i in range(1, steps):
            y = y0 + (y1 - y0) * i / steps
            self.wall(x0 + 0.1, y, x1 - 0.1, y, 0.35)
        self.wall((x0 + x1) / 2, y0, (x0 + x1) / 2, y1, 0.8)

    def dimension(self, x0, y0, x1, y1, value, dx=0, dy=-0.15):
        self.line((X0 + x0 * M, Y0 + y0 * M), (X0 + x1 * M, Y0 + y1 * M), 0.4, RED)
        for x, y in ((x0, y0), (x1, y1)):
            self.line((X0 + x * M - 3, Y0 + y * M - 3), (X0 + x * M + 3, Y0 + y * M + 3), 0.4, RED)
        self.text(X0 + ((x0 + x1) / 2 + dx) * M, Y0 + ((y0 + y1) / 2 + dy) * M, value, 7.5, RED)

    def frame(self, title, number):
        self.shape.draw_rect(pymupdf.Rect(24, 24, 1167, 818))
        self.shape.finish(width=1, color=INK)
        self.shape.draw_rect(pymupdf.Rect(820, 738, 1167, 818))
        self.shape.finish(width=0.8, color=INK)
        self.text(832, 756, 'ნიმუში — გამოგონილი პროექტი', 9, RED)
        self.text(832, 772, 'საცხოვრებელი კორპუსი', 11)
        self.text(832, 790, title, 10)
        self.text(832, 806, f'მასშტაბი 1:110     ფურცელი {number} / 3', 8, THIN)
        self.text(48, 66, title, 15)

    def done(self):
        self.shape.commit()


def typical_floor(doc):
    s = Sheet(doc, 'სართულები 2–9, ტიპიური გეგმა', 'A-02')
    s.room(0, 0, 32, 14, 2.4)
    s.wall(1, 6.45, 30, 6.45)
    s.wall(1, 7.55, 30, 7.55)
    s.wall(1, 6.45, 1, 7.55)
    s.wall(30, 6.45, 30, 7.55)
    # South apartments.
    for x in (8, 16, 24):
        s.wall(x, 7.55, x, 14)
    s.label(2.2, 11, 'ბინა 1   51,6 მ²')
    s.label(18.2, 11, 'ბინა 3   51,6 მ²')
    s.label(26.2, 11, 'ბინა 4   51,6 მ²')
    # Apartment 2, drawn room by room.
    s.wall(8, 10.2, 16, 10.2, 1)
    s.wall(12.4, 7.55, 12.4, 10.2, 1)
    s.wall(14, 7.55, 14, 10.2, 1)
    s.wall(13.65, 10.2, 13.65, 14, 1)
    s.wall(13.65, 11.36, 16, 11.36, 1)
    s.label(8.5, 12.1, 'მისაღები 21,4 მ²')
    s.label(13.72, 12.5, 'საძინებელი 6,2 მ²', 6.5)
    s.label(13.72, 12.95, 'სიგანე 2,35 მ', 6.5)
    s.label(8.3, 9.4, 'საძინებელი 11,7 მ²')
    s.label(12.47, 9.4, 'სველი 4,2 მ²', 6.5)
    s.label(14.1, 9.4, 'სამზარეულო 5,3', 6.5)
    s.label(13.8, 10.9, 'ჰოლი', 6.5)
    s.label(8.5, 13.5, 'ფანჯარა 1,50×1,50')
    for x in (3.5, 10.5, 19.5, 27.5):
        s.door(x, 7.55)
    s.label(9.0, 8.3, 'კარი 90 სმ')
    # North side: cores between two apartments.
    s.wall(9.6, 0, 9.6, 6.45)
    s.wall(25.2, 0, 25.2, 6.45)
    s.label(2.2, 3.2, 'ბინა 5   61,9 მ²')
    s.label(26.6, 3.2, 'ბინა 6   43,9 მ²')
    s.door(5.5, 6.45, up=True)
    s.door(27, 6.45, up=True)
    s.stair(10.4, 2.4, 13.4, 6.45)
    s.label(10.5, 1.6, 'კიბე 1')
    s.label(10.5, 2.1, 'სიგანე 1,20 მ')
    s.stair(21.4, 2.4, 24.4, 6.45)
    s.label(21.5, 1.6, 'კიბე 2')
    s.label(21.5, 2.1, 'სიგანე 1,00 მ')
    s.room(15, 3.2, 17.2, 6.45, 1.8)
    s.room(17.4, 3.2, 19.6, 6.45, 1.8)
    s.label(15.5, 2.9, 'ლიფტები')
    s.door(12, 6.45, 0.75, up=True)
    s.door(22.5, 6.45, 0.75, up=True)
    s.label(11.6, 5.45 + 1.7, 'კარი 75 სმ')
    s.label(21.2, 5.45 + 1.7, 'კარი 75 სმ')
    # Dimensions that matter.
    s.dimension(1, 6.95, 10.4, 6.95, 'ჩიხი 9,40 მ')
    s.dimension(24.4, 6.95, 30, 6.95, 'ჩიხი 5,60 მ')
    s.dimension(13.4, 1.2, 21.4, 1.2, 'კიბეებს შორის 8,00 მ')
    s.dimension(32.6, 6.45, 32.6, 7.55, 'დერეფანი 1,10 მ', dx=0.3, dy=0.1)
    s.label(1.2, 4.6, 'უშორესი სავალი მანძილი 28,6 მ')
    s.label(13.55, 2.2, 'ცეცხლმაქრი', 6.5)
    s.line((X0 + 14.2 * M, Y0 + 2.35 * M), (X0 + 14.2 * M, Y0 + 6.0 * M), 0.4, THIN)
    s.label(19.7, 3.0, 'სახანძრო', 6.5)
    s.label(19.7, 3.35, 'მილდგარი', 6.5)
    s.line((X0 + 20.4 * M, Y0 + 3.5 * M), (X0 + 20.4 * M, Y0 + 6.0 * M), 0.4, THIN)
    s.text(48, 760, 'დატვირთვა: 34 ადამიანი სართულზე.  ბინები: 6 სართულზე, სულ 48.', 9)
    s.done()


def ground_floor(doc):
    s = Sheet(doc, 'სართული 1, გეგმა', 'A-01')
    s.room(0, 0, 32, 14, 2.4)
    s.wall(0, 7.0, 32, 7.0)
    s.stair(10.4, 2.4, 13.4, 6.45)
    s.stair(21.4, 2.4, 24.4, 6.45)
    s.label(10.5, 2.1, 'კიბე 1')
    s.label(21.5, 2.1, 'კიბე 2')
    s.door(10.0, 0, 1.0)
    s.label(7.2, -0.5, 'კიბე 1-ის გასასვლელი გარეთ')
    s.label(14.2, 10.2, 'ფოიე')
    s.label(19.5, 7.8, 'კიბე 2 გადის ფოიეში')
    s.label(3.0, 11, 'სათავსები')
    s.label(25.0, 11, 'ტექნიკური ოთახი')
    # Two main entrances, one with a ramp.
    s.door(13, 14, 1.2, up=True)
    s.door(20, 14, 1.2, up=True)
    s.label(12.4, 14.5, 'მთავარი შესასვლელი 1')
    s.label(18.6, 14.5, 'მთავარი შესასვლელი 2')
    s.label(18.6, 14.95, '3 საფეხური')
    s.room(7.7, 14.3, 12.2, 15.7, 0.8)
    s.label(7.8, 16.2, 'პანდუსი 1:10, h=0,45 მ')
    s.label(0.2, 16.2, 'ავტოსადგომი, 6 ადგილი')
    for i in range(6):
        s.room(0.2 + i * 1.2, 14.3, 1.3 + i * 1.2, 15.8, 0.5)
    s.done()


def section(doc):
    s = Sheet(doc, 'ჭრილი 1-1, კიბე, შენიშვნები', 'A-03')
    left, width = 4, 16
    for level in range(0, 10):
        y = 12 - level * 1.25
        s.wall(left, y, left + width, y, 1.6)
        mark = f'+{level * 3},00' if level else '±0,00'
        s.label(left - 2.4, y + 0.1, mark)
    s.wall(left, 12, left, 0.75, 2.2)
    s.wall(left + width, 12, left + width, 0.75, 2.2)
    s.wall(left, 13.25, left + width, 13.25, 2.2)
    s.wall(left, 12, left, 13.25, 2.2)
    s.wall(left + width, 12, left + width, 13.25, 2.2)
    s.label(left - 2.4, 13.35, '−3,00')
    s.label(left + 0.5, 12.8, 'სარდაფი, დერეფნის ჭერი 2,20 მ')
    s.label(left + 0.5, 11.55, 'ოთახის ჭერი 2,70 მ')
    s.label(left + 0.5, 1.15, 'ზედა დაკავებული იატაკი +24,00')
    s.label(23, 0.6, 'კიბის დეტალი')
    for i in range(8):
        x, y = 23 + i * 0.5, 5 - i * 0.32
        s.wall(x, y, x + 0.5, y, 1)
        s.wall(x + 0.5, y, x + 0.5, y - 0.32, 1)
    s.label(23, 5.6, 'საფეხური 17,5 / 28 სმ')
    s.label(23, 6.1, 'გასავლელის სიმაღლე 2,10 მ')
    notes = ('დანიშნულება: მრავალბინიანი საცხოვრებელი სახლი, სც-2', 'კლასი: IV', 'სართულიანობა: 9 + სარდაფი',
             'ავტოსაშხეფი სისტემა: გათვალისწინებული არ არის', 'კიბის უჯრედის კედლები: ცეცხლმედეგობა 1 სთ',
             'დერეფნის კედლები: ცეცხლმედეგობა 1 სთ', 'სახანძრო-ტექნიკური სიმაღლე: 24,0 მ')
    s.text(800, 470, 'შენიშვნები', 11)
    for i, note in enumerate(notes):
        s.text(800, 490 + i * 16, note, 9)
    s.done()


def where(anchors, text):
    return [a['id'] for a in anchors if text in a['text']][:1]


def result(anchors, rule_id, status, found='', ka='', en='', fix_ka='', fix_en='', at=None, page=None):
    return dict(rule_id=rule_id, status=status, found=found, explanation_ka=ka, explanation_en=en, fix_ka=fix_ka, fix_en=fix_en,
                page=page, anchors=where(anchors, at) if at else [], box=None)


def review(a):
    r = lambda *args, **kwargs: result(a, *args, **kwargs)
    checks = [
        r('1008.1.1', 'fail', '75 სმ', 'კიბე 1-ის კარი 75 სმ-ია, საჭიროა არანაკლებ 82 სმ თავისუფალი სიგანე.', 'The door to stair 1 is 75 cm; at least 82 cm clear width is required.',
          'კარი შეცვალეთ ისეთით, რომლის თავისუფალი სიგანეა ≥ 82 სმ.', 'Use a door with a clear width of at least 82 cm.', at='კარი 75 სმ'),
        r('1009.4', 'fail', '1,00 მ', 'კიბე 2-ის სიგანე 1,00 მ-ია, მინიმუმი 1,1 მ.', 'Stair 2 is 1.00 m wide; the minimum is 1.1 m.',
          'კიბის თავისუფალი სიგანე გაზარდეთ 1,1 მ-მდე მაინც.', 'Widen the stair to at least 1.1 m clear.', at='სიგანე 1,00 მ'),
        r('1018.2', 'fail', '1,10 მ', 'საერთო დერეფანი 1,10 მ-ია. სც-2 მრავალბინიანი სახლის საერთო დერეფანზე 90 სმ-იანი შეღავათი არ ვრცელდება, მინიმუმია 1,2 მ.',
          'The common corridor is 1.10 m. The 90 cm allowance does not cover common corridors of სც-2 apartment buildings, so the minimum is 1.2 m.',
          'დერეფანი გააფართოვეთ 1,2 მ-მდე.', 'Widen the corridor to 1.2 m.', at='დერეფანი 1,10 მ'),
        r('1018.4', 'fail', '9,40 მ', 'დასავლეთის ჩიხი 9,40 მ-ია. შენობა არ არის დაშხეფებული, ლიმიტი 6,0 მ.', 'The west dead end is 9.40 m. The building has no sprinklers, so the limit is 6.0 m.',
          'შეამცირეთ ჩიხი 6,0 მ-მდე, ან დაამატეთ გასასვლელი.', 'Shorten the dead end to 6.0 m or add an exit.', at='ჩიხი 9,40 მ'),
        r('403.5.1', 'fail', '8,00 მ', 'შენობა მაღლივია (+24,00). კიბეებს შორის 8,00 მ-ია, საჭიროა 9,0 მ ან დიაგონალის მეოთხედი (რომელიც ნაკლებია).',
          'The building is high-rise (+24.00). The stairs are 8.00 m apart; 9.0 m or a quarter of the diagonal is required, whichever is less.',
          'კიბეები ერთმანეთს დააშორეთ სულ მცირე 9,0 მ-ით.', 'Move the stairs at least 9.0 m apart.', at='კიბეებს შორის 8,00 მ'),
        r('1010.3', 'fail', '1:10', 'პანდუსის დახრა 1:10-ია, მაქსიმუმი 1:12.', 'The ramp slope is 1:10; the maximum is 1:12.',
          'პანდუსი დააგრძელეთ: h=0,45 მ-ზე საჭიროა სულ მცირე 5,4 მ სიგრძე.', 'Lengthen the ramp: a 0.45 m rise needs at least 5.4 m.', at='პანდუსი 1:10'),
        r('1105.1', 'fail', '1 / 2 (50%)', 'ორი მთავარი შესასვლელიდან მისაწვდომია ერთი, საჭიროა 60%.', 'One of two main entrances is accessible; 60% is required.',
          'მთავარ შესასვლელ 2-ს დაუმატეთ პანდუსი.', 'Add a ramp to main entrance 2.', at='მთავარი შესასვლელი 2'),
        r('1022.2', 'fail', '1 სთ', 'კიბე აერთებს 4-ზე მეტ სართულს, ამიტომ საჭიროა 2 სთ. ჩანაწერში 1 სთ-ია.', 'The stair connects more than 4 storeys, so 2 h is required. The note says 1 h.',
          'კიბის უჯრედის კედლებისთვის მიუთითეთ 2 სთ ცეცხლმედეგობა.', 'Specify 2 h for the stair enclosure walls.', at='კიბის უჯრედის კედლები'),
        r('1003.2', 'fail', '2,20 მ', 'სარდაფის დერეფნის ჭერი 2,20 მ-ია, მინიმუმი 2,3 მ.', 'The basement corridor ceiling is 2.20 m; the minimum is 2.3 m.',
          'გაზარდეთ სიმაღლე 2,3 მ-მდე.', 'Raise the ceiling to at least 2.3 m.', at='დერეფნის ჭერი 2,20 მ'),
        r('1208.3', 'fail', '6,2 მ²', 'ბინა 2-ის საძინებელი 6,2 მ²-ია, სხვა საცხოვრებელი ოთახის მინიმუმი 7,0 მ².', 'The bedroom in apartment 2 is 6.2 m²; the minimum for other habitable rooms is 7.0 m².',
          'ოთახის ფართობი გაზარდეთ 7,0 მ²-მდე.', 'Enlarge the room to at least 7.0 m².', at='საძინებელი 6,2 მ²'),
        r('403.4.5', 'missing', '', 'შენობა მაღლივია, მაგრამ ხანძრის საკონტროლო ცენტრი გეგმაზე არ ჩანს.', 'The building is high-rise, but no fire command centre appears on the plans.',
          'დაამატეთ ოთახი და ადგილი შეათანხმეთ სახანძრო დანაყოფთან.', 'Add the room and agree its location with the fire service.', page=1),
        r('1106.1', 'missing', '6 ადგილი', 'ავტოსადგომზე მისაწვდომი ადგილი მონიშნული არ არის.', 'No accessible space is marked in the car park.',
          'მონიშნეთ სულ მცირე ერთი მისაწვდომი ადგილი.', 'Mark at least one accessible space.', at='ავტოსადგომი, 6 ადგილი'),
        r('1107.6.2.1.1', 'missing', '48 ბინა', 'შენობაში 48 ბინაა, საჭიროა სულ მცირე 2% ა ტიპის ერთეული. გეგმაზე არცერთი არ არის მონიშნული.', 'There are 48 apartments, so at least 2% Type A units are required. None is marked.',
          'მონიშნეთ სულ მცირე 1 ა ტიპის ერთეული.', 'Mark at least 1 Type A unit.', at='ბინები: 6 სართულზე'),
        r('1011.1', 'verify', '', 'გასასვლელის ნიშნები ამ ფურცლებზე არ ჩანს. შესაძლოა ელექტროობის ნახაზებზეა.', 'Exit signs do not appear on these sheets. They may be on the electrical sheets.',
          'დაამატეთ ელექტროობის ან ევაკუაციის ნახაზი.', 'Add the electrical or evacuation sheet.'),
        r('907.2.9.1', 'verify', '48 ბინა', 'საჭიროა განგაშის სისტემა (16-ზე მეტი ერთეული), მაგრამ ამ ფურცლებზე არ ჩანს.', 'A fire alarm is required (more than 16 units), but it does not appear on these sheets.',
          'დაამატეთ სუსტი დენების ნახაზი.', 'Add the low-voltage sheet.'),
        r('1027.1', 'verify', '', 'კიბე 2 ფოიეში გადის. ეს დასაშვებია მხოლოდ 1027.1-ის გამონაკლისების პირობებში.', 'Stair 2 discharges into the lobby. That is allowed only under the exceptions of 1027.1.',
          'შეამოწმეთ გამონაკლისის პირობები.', 'Check the conditions of the exception.', at='კიბე 2 გადის ფოიეში'),
        r('1015.2.1', 'verify', '8,00 მ', 'მაღლივში კიბეების დაშორებას 403.5.1 არეგულირებს; შედეგი იხილეთ იქ.', 'In a high-rise, stair separation is set by 403.5.1: see that result.', at='კიბეებს შორის 8,00 მ'),
        r('915.12', 'verify', '24,0 მ', 'სიმაღლე 30 მ-ს არ აღემატება, ამ პუნქტის მოთხოვნა სც-2-ზე არ უნდა გავრცელდეს, მაგრამ გენგეგმა ფაილში არ არის. 915-ე ქვეთავი 2027 წლის 1 მარტამდე შეჩერებულია სახელმწიფო სახანძრო ზედამხედველობის გარეშე ობიექტებისთვის.',
          'The height is under 30 m, so this should not apply to სც-2, but there is no site plan in the file. Section 915 is suspended until 1 March 2027 for objects outside state fire supervision.',
          'დაამატეთ გენგეგმა.', 'Add the site plan.', at='სახანძრო-ტექნიკური სიმაღლე'),
    ]
    passes = {
        'Art. 2': ('IV კლასი', 'კლასი: IV'), '302.1': ('სც-2', 'დანიშნულება:'), '202': ('მაღლივი, +24,00', 'ზედა დაკავებული იატაკი'),
        '1004.1.2': ('34 ადამიანი სართულზე', 'დატვირთვა: 34'), '1005.3.1': ('34 × 7,6 მმ = 26 სმ', 'სიგანე 1,20 მ'), '1005.3.2': ('34 × 5,1 მმ = 17 სმ', 'კარი 90 სმ'),
        '1009.5': ('2,10 მ', 'გასავლელის სიმაღლე'), '1009.7.2': ('17,5 / 28 სმ', 'საფეხური 17,5'), '1016.2': ('28,6 მ', 'უშორესი სავალი მანძილი'),
        '1021.2': ('2 კიბე', 'კიბე 1'), '903.2.8': ('+24,00 < 37 მ', 'ავტოსაშხეფი სისტემა'), '403.3': ('+24,00 < 37 მ', 'ავტოსაშხეფი სისტემა'),
        '403.4.3': ('მილდგარი', 'მილდგარი'), '906.1': ('ცეცხლმაქრი', 'ცეცხლმაქრი'), '1018.1': ('1 სთ', 'დერეფნის კედლები'),
        '1205.2': ('2,25 მ² / 21,4 მ² = 11%', 'ფანჯარა 1,50×1,50'), '1208.1': ('2,35 მ', 'სიგანე 2,35 მ'), '1208.2': ('2,70 მ', 'ოთახის ჭერი 2,70 მ'),
    }
    checks += [r(rule, 'pass', found, at=at) for rule, (found, at) in passes.items()]
    done = {c['rule_id'] for c in checks}
    checks += [r(rule['id'], 'not_applicable') for rule in RULES if rule['id'] not in done]
    assert all(c['rule_id'] in BY_ID for c in checks)
    return dict(checks=checks, building=dict(
        name='საცხოვრებელი კორპუსი (ნიმუში)', occupancy='სც-2', storeys=9, top_floor_m=24.0, high_rise=True, sprinklered=False,
        summary_ka='9-სართულიანი მაღლივი მრავალბინიანი სახლი სარდაფით, 48 ბინა, ავტოსაშხეფი სისტემის გარეშე.',
        summary_en='9-storey high-rise apartment building with a basement, 48 apartments, no sprinklers.'))


def main():
    OUT.mkdir(exist_ok=True)
    doc = pymupdf.open()
    ground_floor(doc)
    typical_floor(doc)
    section(doc)
    doc.set_metadata(dict(title='NORMA sample project', author='NORMA'))
    doc.save(OUT / 'sample.pdf', garbage=4, deflate=True)
    anchors = pdf_tools.anchors(OUT / 'sample.pdf')
    (OUT / 'review.json').write_text(json.dumps(review(anchors), ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(anchors), 'text items')


if __name__ == '__main__':
    main()
