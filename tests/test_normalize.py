"""フォロー判定の正規化と、速納の売り切れ判定の小さなテスト。

実行: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from main import normalize_for_match as norm  # noqa: E402
from scrapers.sokuno import SokunoScraper  # noqa: E402


def hit(text, keyword):
    return norm(keyword) in norm(text)


class NormalizeTest(unittest.TestCase):
    def test_kana_dash_variants(self):
        # カタカナに挟まれたハイフン類・長音はすべて「ー」になる
        for dash in "ー-‐‑‒–—―−－ｰ":
            self.assertEqual(norm(f"バイポ{dash}ラ電源"), "バイポーラ電源", repr(dash))

    def test_sokuno_pbz(self):
        self.assertTrue(hit("菊水電子工業 バイポ-ラ電源　PBZ40-10", "バイポーラ"))
        self.assertTrue(hit("PBZ20-20(With LAN)　バイポ-ラ電源", "バイポーラ"))
        self.assertTrue(hit("菊水電子工業 バイポ-ラ電源　PBZ40-10", "pbz"))

    def test_model_hyphens_kept(self):
        self.assertEqual(norm("PBZ40-10"), "pbz40-10")
        self.assertTrue(hit("キーエンス VK-X200", "VK-X"))
        self.assertTrue(hit("Alpha-Step IQ", "alpha-step"))
        self.assertTrue(hit("日立 SPA-400", "spa-400"))
        self.assertFalse(hit("日立 SPA400", "spa-400"))
        # カタカナの片側だけに接するハイフンは残す
        self.assertEqual(norm("ケーブル-A"), "ケーブル-a")
        self.assertEqual(norm("ア-1"), "ア-1")

    def test_nfkc(self):
        self.assertEqual(norm("ＶＫ－Ｘ２００"), "vk-x200")
        self.assertEqual(norm("ﾊﾞｲﾎﾟｰﾗ"), "バイポーラ")
        self.assertTrue(hit("ＮＩ ２ＣＨ ＳＭＵシステム", "smu"))
        self.assertTrue(hit("直流電圧／電流発生器", "電圧/電流発生器"))
        # 中黒はハイフン扱いしない
        self.assertEqual(norm("ネットワーク・アナライザ"), "ネットワーク・アナライザ")

    def test_exclude_normalized(self):
        # 除外語も同じ正規化で効く(全角・ハイフン表記の揺れ)
        self.assertTrue(hit("ﾄﾗﾝｼﾞｽﾀ特性", "トランジスタ"))
        self.assertTrue(hit("バイポ-ラプレート", "バイポーラプレート"))


SOKUNO_PAGE = """<html><body><ul>
<li><div class="detail">
 <p class="name"><a href="/shopdetail/000000001187/ct-CHU_ALL/page9/order/">【中古】菊水電子工業　バイポ-ラ電源　PBZ40-10</a></p>
 <p class="price"><em class="price">337,000円（税抜）</em></p>
 <div class="else"><ul class="clear"><li>菊水電子工業</li><li></li><li>2111271</li></ul></div>
 <p class="quantity"><span class="M_item-stock-soldout M_category-soldout">売り切れ</span></p>
</div></li>
<li><div class="detail">
 <p class="name"><a href="/shopdetail/000000008229/ct-CHU_ALL/page1/order/">【中古】横河計測　GS200　直流電圧/電流源</a></p>
 <p class="price"><em class="price">100,000円（税抜）</em></p>
 <div class="else"><ul class="clear"><li>横河計測</li><li></li><li>1234567</li></ul></div>
 <p class="quantity"><span class="M_item-stock-smallstock M_category-smallstock">残りあと1個</span></p>
</div></li>
</ul></body></html>"""


class SokunoSoldOutTest(unittest.TestCase):
    def test_parse_sold_flag(self):
        sc = SokunoScraper()
        rows = sc._parse_list_page(BeautifulSoup(SOKUNO_PAGE, "lxml"))
        self.assertEqual([(it.uid, sold) for it, sold in rows],
                         [("000000001187", True), ("000000008229", False)])

    def test_fetch_drops_sold(self):
        sc = SokunoScraper(request_interval=0)
        pages = {1: SOKUNO_PAGE}
        sc.get_soup = lambda url: BeautifulSoup(
            pages.get(int(url.rstrip("/").rsplit("page", 1)[1]), "<html></html>"), "lxml")
        items = sc.fetch_listings()
        self.assertEqual([it.uid for it in items], ["000000008229"])
        self.assertEqual(sc.sold_out_uids, {"000000001187"})


if __name__ == "__main__":
    unittest.main()
