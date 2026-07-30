from jsonschema import Draft202012Validator
from src.extraction import lmm_extractor
from src.utils.config_loader import load_extraction_schema
validator = Draft202012Validator(load_extraction_schema())
print(lmm_extractor.estrai_singolo('SDN', '2023-Q2', validator))