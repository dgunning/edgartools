"""Tests for reverse_name — SEC name reversal."""
import pytest

from edgar.display.formatting import reverse_name


class TestReverseName:
    """Core cases: standard SEC names."""

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("WALKER KYLE", "Kyle Walker"),
        ("KONDO CHRIS", "Chris Kondo"),
        ("KONDO CHRIS Jr", "Chris Kondo Jr"),
        ("KONDO CHRIS Jr.", "Chris Kondo Jr."),
        ("KONDO CHRIS Jr ET AL", "Chris Kondo Jr ET AL"),
        ("KONDO CHRIS Jr et al", "Chris Kondo Jr et al"),
        ("KONDO CHRIS Jr et al.", "Chris Kondo Jr et al."),
        ("JAMES HAMILTON E", "Hamilton E James"),
        ("BURNS BENJAMIN MICHAEL", "Benjamin Michael Burns"),
        ("FROST PHILLIP MD", "Phillip Frost MD"),
        ("FROST PHILLIP MD ET AL", "Phillip Frost MD ET AL"),
        ("Borninkhof K. Michelle", "Michelle K. Borninkhof"),
        ("Bennett C Frank", "Frank C Bennett"),
        ("Frank Thomas AJ", "Thomas Aj Frank"),
        ("FOSTER WATT R JR", "Watt R Foster JR"),
        ("WATT", "Watt"),
        ("O'CONNELL BENJAMIN", "Benjamin O'Connell"),
    ])
    def test_standard_names(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestMultiWordSurnames:

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("VAN DEMAN ERIC MATTHEW", "Eric Matthew Van Deman"),
        ("van den Boom Esther", "Esther Van Den Boom"),
        ("van der Post Kuno D", "Kuno D Van Der Post"),
        ("DE LA SERNA JUAN MARTIN", "Juan Martin De La Serna"),
        ("Del Rio Francisco Javier", "Francisco Javier Del Rio"),
        ("Di Cicco John", "John Di Cicco"),
        ("St George Martin J", "Martin J St George"),
        ("EL KHODR MOUDY", "Moudy El Khodr"),
        ("VON HAGEN WILHELM", "Wilhelm Von Hagen"),
        ("DU PONT ALEXIS", "Alexis Du Pont"),
        ("DA SILVA MARCOS ANTONIO", "Marcos Antonio Da Silva"),
        ("DEN HARTOG JOHN", "John Den Hartog"),
        ("TEN EYCK PETER", "Peter Ten Eyck"),
    ])
    def test_multi_word_surnames(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestSuffixes:

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("GRAHAM WILLIAM A IV", "William A Graham IV"),
        ("JOULLIAN EDWARD C IV", "Edward C Joullian IV"),
        ("Eckert William James IV", "William James Eckert IV"),
    ])
    def test_iv_suffix(self, input_name, expected):
        assert reverse_name(input_name) == expected

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("LEFAIVRE RICHARD A PHD", "Richard A Lefaivre PHD"),
        ("Templeton Mary B Esq", "Mary B Templeton Esq"),
        ("LAMBE RONAN DR", "Ronan Lambe DR"),
        ("SALDI JUGAN DR", "Jugan Saldi DR"),
        ("SANDAGE BOBBY W. JR., PHD.", "Bobby W. Sandage JR., PHD."),
    ])
    def test_professional_suffixes(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestTitlePrefixes:

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("DR WEINSTEIN LEONARD L", "Dr Leonard L Weinstein"),
        ("DR BHATTACHARYYA PRANAB", "Dr Pranab Bhattacharyya"),
    ])
    def test_title_prefix(self, input_name, expected):
        assert reverse_name(input_name) == expected

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("Judge John P", "John P Judge"),
        ("JUDGE ALISA", "Alisa Judge"),
        ("Hon Hsiao-Wuen", "Hsiao-Wuen Hon"),
        ("HON PETER", "Peter Hon"),
    ])
    def test_judge_hon_are_surnames(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestMiddleInitials:

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("SPERANZA ERNEST V", "Ernest V Speranza"),
        ("BILLER KENNETH V", "Kenneth V Biller"),
        ("Smith David V", "David V Smith"),
    ])
    def test_v_is_middle_initial(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestSpecialCharacters:

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("O'Donnell James C.", "James C. O'Donnell"),
        ("O'BRIEN PATRICK", "Patrick O'Brien"),
        ("O'Toole Amie Thuener", "Amie Thuener O'Toole"),
    ])
    def test_apostrophe_names(self, input_name, expected):
        assert reverse_name(input_name) == expected

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("Stevens-Kittner Gerald", "Gerald Stevens-Kittner"),
        ("GARCIA-LOPEZ MARIA", "Maria Garcia-Lopez"),
    ])
    def test_hyphenated_names(self, input_name, expected):
        assert reverse_name(input_name) == expected

    @pytest.mark.fast
    @pytest.mark.parametrize("input_name, expected", [
        ("LO MARIANNA", "Marianna Lo"),
        ("Lo Marianna", "Marianna Lo"),
        ("WU JIN XU", "Jin Xu Wu"),
        ("Qi Guosheng", "Guosheng Qi"),
        ("NI SAIJUN", "Saijun Ni"),
    ])
    def test_short_last_names(self, input_name, expected):
        assert reverse_name(input_name) == expected


class TestEdgeCases:

    @pytest.mark.fast
    def test_single_word(self):
        assert reverse_name("WATT") == "Watt"

    @pytest.mark.fast
    def test_empty_string(self):
        assert reverse_name("") == ""

    @pytest.mark.fast
    def test_two_word_standard(self):
        assert reverse_name("SMITH JOHN") == "John Smith"

    @pytest.mark.fast
    def test_mixed_case_preserved_as_title(self):
        assert reverse_name("smith john a") == "John A Smith"

    @pytest.mark.fast
    def test_et_al(self):
        assert reverse_name("KARMANOS PETER JR ET AL") == "Peter Karmanos JR ET AL"
