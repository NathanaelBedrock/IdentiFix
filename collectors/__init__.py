from collectors.base import BaseCollector
from collectors.sherlock_collector import SherlockCollector
from collectors.maigret_collector import MaigretCollector
from collectors.holehe_collector import HolehCollector
from collectors.blackbird_collector import BlackbirdCollector
from collectors.h8mail_collector import H8mailCollector
from collectors.socialscan_collector import SocialscanCollector
from collectors.socid_extractor_collector import SocidExtractorCollector
from collectors.exifread_collector import ExifReadCollector
from collectors.saucenao_collector import SauceNAOCollector
from collectors.naminter_collector import NaminterCollector
from collectors.gitfive_collector import GitFiveCollector
from collectors.linkook_collector import LinkookCollector
from collectors.sociopath_collector import SociopathCollector
from collectors.sharetrace_collector import ShareTraceCollector
from collectors.nametrace_collector import NameTraceCollector

ALL_COLLECTORS: list[type[BaseCollector]] = [
    SherlockCollector,
    MaigretCollector,
    HolehCollector,
    BlackbirdCollector,
    H8mailCollector,
    SocialscanCollector,
    SocidExtractorCollector,
    ExifReadCollector,
    SauceNAOCollector,
    NaminterCollector,
    GitFiveCollector,
    LinkookCollector,
    SociopathCollector,
    ShareTraceCollector,
    NameTraceCollector,
]


def get_collector_instances() -> list[BaseCollector]:
    return [cls() for cls in ALL_COLLECTORS]
