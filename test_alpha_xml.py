from pptx.oxml import OxmlElement
from pptx.oxml import parse_xml
from pptx.oxml.ns import qn
import xml.etree.ElementTree as ET

alpha_pct = 5098

# Method 1
alpha1 = parse_xml(f'<a:alpha xmlns:a="{qn("a:alpha").split("}")[0][1:]}" val="{alpha_pct}"/>')

# Method 2
alpha2 = OxmlElement('a:alpha')
alpha2.set('val', str(alpha_pct))

print(ET.tostring(alpha1).decode())
print(ET.tostring(alpha2).decode())
