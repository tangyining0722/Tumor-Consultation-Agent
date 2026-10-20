import requests
import xml.etree.ElementTree as ET
from .schemas import EvidenceItem

API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def search_pubmed(query: str, email: str = "", limit: int = 5) -> list[EvidenceItem]:
    if not query.strip():
        return []
    params = {"db":"pubmed", "term":query[:300], "retmax":max(1,min(limit,10)), "retmode":"json", "tool":"MediCouncilEducation"}
    if email: params["email"] = email
    r = requests.get(API+"esearch.fcgi", params=params, timeout=18)
    r.raise_for_status()
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids: return []
    params2 = {"db":"pubmed", "id":",".join(ids), "retmode":"xml", "tool":"MediCouncilEducation"}
    if email: params2["email"] = email
    r2 = requests.get(API+"efetch.fcgi", params=params2, timeout=25)
    r2.raise_for_status()
    root = ET.fromstring(r2.content)
    items=[]
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//MedlineCitation/PMID", default="")
        title_node = article.find(".//ArticleTitle")
        title = "".join(title_node.itertext()).strip() if title_node is not None else ""
        abstracts = ["".join(node.itertext()).strip() for node in article.findall(".//Abstract/AbstractText")]
        year = article.findtext(".//PubDate/Year", default="")
        if pmid:
            items.append(EvidenceItem(pmid=pmid,title=title,abstract=" ".join(abstracts),url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",publication=year))
    return items
