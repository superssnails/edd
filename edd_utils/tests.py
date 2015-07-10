
from __future__ import division
from edd_utils.parsers.excel import *
from edd_utils.form_utils import *
from edd_utils.parsers import gc_ms
from edd_utils.parsers import skyline
from django.test import TestCase
from cStringIO import StringIO
import os

test_dir = os.path.join(os.path.dirname(__file__), "fixtures", "misc_data")

########################################################################
# GC-MS
class GCMSTests (TestCase) :
    def test_1 (self) :
        test_file = os.path.join(test_dir, "gc_ms_1.txt")
        l = gc_ms.run([test_file], out=StringIO(), err=StringIO())
        assert len(l.samples) == 102
        #l.find_consensus_peaks(show_plot=True)
        err = StringIO()
        out = StringIO()
        l.show_peak_areas(out=out, err=err)
        assert ("0059.D          562         None         None" in
            out.getvalue())
        assert ("0062.D       104049      1192526        35926" in
            out.getvalue())
        assert ("WARNING: 2 peaks near 8.092 for sample 0062.D" in
            err.getvalue())
        assert (err.getvalue().count("WARNING") == 44)
        err = StringIO()
        out = StringIO()
        l.show_peak_areas_csv(out=out, err=err)
        assert ("0059.D,562,None,None" in out.getvalue())
        assert ("0062.D,104049,1192526,35926" in out.getvalue())

    def test_2 (self) :
        # a slightly different format
        #
        test_file = os.path.join(test_dir, "gc_ms_2.txt")
        l = gc_ms.run([test_file], out=StringIO(), err=StringIO())
        assert len(l.samples) == 5, len(l.samples)
        #print l.find_consensus_peaks()
        err = StringIO()
        out = StringIO()
        l.show_peak_areas(out=out, err=err)
        assert (out.getvalue() == """\
          ID       Peak 1       Peak 2       Peak 3       Peak 4
  0827.a24.D       197080      1830086       849878       702183
    0827a1.D       440937      1740194       684256       822430
   0827a12.D       304791      1490375       580788       833538
   0827a17.D        95305       613903       408431       625373
   0827a24.D       197080      1830086       849878       702183
"""), "'%s'" % out.getvalue()
        #
        # Fault tolerance
        #
        test_file = os.path.join(test_dir, "skyline.csv")
        try :
            l = gc_ms.run([test_file], out=StringIO(), err=StringIO())
        except ValueError :
            pass
        else :
            assert False

    def test_xls_key (self) :
        #
        # Import .xlsx workbook
        #
        test_file = os.path.join(test_dir, "sample_gc_ms_key.xlsx")
        headers, table = gc_ms.import_xlsx_metadata(open(test_file, "rb"))
        assert (headers == [u'sample ID (could be vial #)', u'label to display', u'parent strain', u'plasmid/change', u'colony number', u'time point', u'media (induction, etc.)', u'sample type', None, u'user field 1', u'user field 2', u'user field 3'])


########################################################################
# SKYLINE
class SkylineTests (TestCase) :
    def test_1 (self) :
        from cStringIO import StringIO
        file_name = os.path.join(test_dir, "skyline.csv")
        data = open(file_name, "U").read().splitlines()
        out = StringIO()
        r = skyline.ParseCSV(data).show_by_protein(out=out).export()
        assert (out.getvalue().startswith("File   A   B   C   D"))
        assert ("4  22  35  35  23" in out.getvalue())
        assert (['4', 'A', 22] in r['rows'])

########################################################################
# EXCEL IMPORT
def get_table () :
  return [
    ["Some random text we want to ignore", None, None, None, None, None],
    ["More random", 2.5, None, None, None, None],
    [None, None, None, None, None, None],
    [None, None, None, None, None, None],
    [None, "sample ID", "line ID", "replica", "molecule1", "molecule 2"],
    [None, "abcd1", "line1", 1, 5.5, 6.5],
    [None, "abcd2", "line1", 2, 4.0, 7.3],
    [None, "abcd3", "line2", 1, 3.5, 8.8],
    [None, "abcd4", "line2", 2, 2.0, 9.6],
    [None, None, None, None, None, None],
    ["Summary line", None, None, None, 3.75, 8.05],
    [None, None, None, None, None, None],
  ]

def make_simple (t, file_name) :
  return export_to_xlsx(t, file_name=file_name, title=file_name)

class ExcelTests (TestCase):
    def test_simple (self) :
        make_simple(get_table(), "tst1.xlsx")
        result = import_xlsx_tables("tst1.xlsx")
        t = result['worksheets'][0][0]
        assert (t['headers'] == [u'sample ID', u'line ID', u'replica',
                u'molecule1', u'molecule 2'])
        assert (t['values'] ==
          [[u'abcd1', u'line1', 1, 5.5, 6.5],
           [u'abcd2', u'line1', 2, 4, 7.3],
           [u'abcd3', u'line2', 1, 3.5, 8.8],
           [u'abcd4', u'line2', 2, 2, 9.6]])
        result2 = import_xlsx_tables("tst1.xlsx",
            worksheet_name="tst1.xlsx",
            column_search_text="sample")
        t2 = result2['worksheets'][0][0]
        assert t2 == t
        result3 = import_xlsx_table("tst1.xlsx") # note different function
        assert result3 == t
        result4 = import_xlsx_table("tst1.xlsx",
            column_labels=["sample id", "molecule1", "MOLECULE 2"])
        assert (result4 == {
            'headers': [u'sample ID', u'molecule1', u'molecule 2'],
            'values': [[u'abcd1', 5.5, 6.5],
                       [u'abcd2', 4, 7.3],
                       [u'abcd3', 3.5, 8.8],
                       [u'abcd4', 2, 9.6]]})
        os.remove("tst1.xlsx")

    def test_error_handling (self) :
        # now screw with the format
        t2 = get_table()
        t2[7][0] = "Extra"
        make_simple(t2, "tst2.xlsx")
        try :
            result = import_xlsx_tables("tst2.xlsx")
        except ValueError :
            pass
        else :
            assert False
        os.remove("tst2.xlsx")
        t3 = get_table()
        t3[7][1] = None
        make_simple(t3, "tst3.xlsx")
        result = import_xlsx_tables("tst3.xlsx")
        assert (result == { 'worksheets': [
            [{'headers': [u'sample ID', u'line ID', u'replica', u'molecule1',
                        u'molecule 2'],
                'values': [[u'abcd1', u'line1', 1, 5.5, 6.5],
                       [u'abcd2', u'line1', 2, 4, 7.3]]}]
            ]})
        try :
            result2 = import_xlsx_table("tst3.xlsx", followed_by_blank_row=True)
        except ValueError :
            pass
        else :
            assert False
        # ask for missing worksheet
        try :
            result = import_xlsx_table("tst3.xlsx", worksheet_name="foo")
        except KeyError :
            pass
        else :
            assert False
        os.remove("tst3.xlsx")

    def test_non_numeric (self) :
        t = get_table()

########################################################################
# OTHER
class UtilsTests (TestCase) :
    def test_form_handling (self) :
        form = {
          'int1' : "1",
          'float1' : "2.5",
          'int2' : "1.5",
          'float2' : "2",
          'int3' : ["1", "2", "3"],
          'float3' : ["1.5"],
          'int4' : ["1.5", "2", "3"],
          'float4' : "",
          'str1' : "foo",
          'str2' : ["foo", "bar"],
          'str3' : "",
        }
        assert (extract_integers_from_form(form, "int1") == 1)
        assert (extract_floats_from_form(form, "int1") == 1.0)
        assert (extract_integers_from_form(form, "int3", allow_list=True) ==
            [1,2,3])
        assert (extract_floats_from_form(form, 'float3', allow_list=True) ==
            [1.5])
        assert (extract_non_blank_string_from_form(form, 'str1') == "foo")
        assert (extract_non_blank_string_from_form(form, 'str2',
            allow_list=True) == ["foo", "bar"])
        try :
            extract_integers_from_form(form, "int3")
        except TypeError :
            pass
        else :
            assert False
        try :
            extract_integers_from_form(form, 'int2')
        except ValueError :
            pass
        else :
            assert False
        try :
            extract_integers_from_form(form, 'int5')
        except KeyError :
            pass
        else :
            assert False
        try :
            extract_integers_from_form(form, 'int4', allow_list=True)
        except ValueError :
            pass
        else :
            assert False
        try :
            extract_non_blank_string_from_form(form, 'str3')
        except ValueError :
            pass
        else :
            assert False
        assert (extract_non_blank_string_from_form(form, 'str3',
                return_none_if_missing=True) is None)
        assert (extract_floats_from_form(form, 'float4',
                return_none_if_missing=True) is None)