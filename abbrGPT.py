import json
from pathlib import Path
from openai import OpenAI

def load_api_key(
    config_path: Path = Path(__file__).parent / "cfg" / "openai_key.json"
) -> str:
    return json.loads(config_path.read_text())["api_key"]

client = OpenAI(api_key=load_api_key())

system_prompt = (
    "You are an abbreviation expert. When given a timetable phrase, pick two to three most representative words "
    "and produce their abbreviations using these rules:\n"
    "1. Preserve any existing all-caps acronyms unchanged.\n"
    "2. Short words perserve first 3 letters;\n"
    "3. Common biomedical terms can apply common abbreviations;\n"
    "4. Otherwise, remove all vowels (A, E, I, O, U), drop non-alphanumerics, then take three to four consonants and uppercase them.\n"
    "5. Return only two or three final abbreviated words, separated by spaces—no extra text.\n"
    "Abbreviation example:\n"
    "Writing session DRG paper -> DRG PPR\n"
    "Pack materials to sterilize for CT -> STRL CT\n"
    "NHP spinal cord RNA-seq -> NHP SC RNA"
)

def abbreviateBatch(
    phrases: list[str],
    model: str = "gpt-4.1",
    temperature: float = 0.3
) -> str:
    batched_prompt = "For each of the following phrases, return only the abbreviation as per the rules:\n\n" + \
                     "\n".join(f"{i+1}. {p}" for i, p in enumerate(phrases))

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": batched_prompt}
        ],
        temperature=temperature,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()

if __name__ == "__main__":
    examples = [
        "Writing session DRG paper",
        "Pack materials to sterilize for CT",
        "Important Tsinghua Program update",
        "NHP spinal cord RNA-seq"
    ]
    print(abbreviateBatch(examples))
