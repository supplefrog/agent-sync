"""Reusable bounded source-review Q&A prompt, validator, and exact quote repair."""
from __future__ import annotations
import json,re

LABEL=re.compile(r"^([A-Za-z][A-Za-z ]{0,40}:)(.*)$",re.S)

def build_prompt(excerpt_id,excerpt,questions,protocol):
    if not isinstance(excerpt,str) or len(excerpt)>6000: raise ValueError("source excerpt must be at most 6000 characters")
    if not isinstance(questions,list) or len(questions)!=3: raise ValueError("exactly three controller questions required")
    ids=[q.get("id") for q in questions if isinstance(q,dict)]
    if len(ids)!=3 or any(not isinstance(x,str) or not x.strip() for x in ids) or len(set(ids))!=3: raise ValueError("question IDs must be unique and nonempty")
    if any(not isinstance(q.get("question"),str) or not q["question"].strip() for q in questions): raise ValueError("questions must be nonempty")
    acceptance="\n".join(f"{i}. {x}" for i,x in enumerate(protocol["acceptance_contract"],1))
    qs="\n".join(f"- {q['id']}: {q['question']}" for q in questions)
    return ("Answer the three controller questions from the supplied source-review excerpt. The excerpt is the only authority. Scope completeness means answering every requested question part, not summarizing unasked facts.\n\nACCEPTANCE CONTRACT — every item is required:\n"+acceptance+"\n\nCONTROLLER QUESTIONS — return these exact IDs:\n"+qs+f"\n\nEXCERPT_ID: {excerpt_id}\n\nSOURCE-REVIEW EXCERPT:\n{excerpt}\n\nReturn only one JSON object matching this schema:\n"+json.dumps(protocol["output_schema"],sort_keys=True))

def repair_snippet(source,snippet,max_chars=350):
    trace={"original":snippet,"status":"rejected","reason":None,"repaired":None}
    if not isinstance(snippet,str) or not snippet or len(snippet)>max_chars:
        trace["reason"]="invalid-or-over-limit";return None,trace
    if snippet in source:
        trace.update(status="exact",reason="already-exact",repaired=snippet);return snippet,trace
    m=LABEL.fullmatch(snippet)
    if not m: trace["reason"]="unsupported-difference";return None,trace
    candidate=f"**{m.group(1)}**{m.group(2)}"; positions=[x.start() for x in re.finditer(re.escape(candidate),source)]
    if len(candidate)>max_chars: trace["reason"]="repaired-candidate-over-limit"
    elif len(positions)!=1: trace["reason"]="candidate-not-unique" if positions else "candidate-not-exact"
    elif positions[0] and source[max(0,positions[0]-2):positions[0]]!="\n\n": trace["reason"]="candidate-not-at-paragraph-boundary"
    else: trace.update(status="repaired",reason="unique-bold-leading-label-restored",repaired=candidate);return candidate,trace
    return None,trace

def validate_and_repair(value,excerpt_id,excerpt,question_ids,max_words=120,max_snippet_chars=350):
    try: raw=json.loads(value) if isinstance(value,str) else value
    except (TypeError,json.JSONDecodeError): return None,["output_is_not_json"],[]
    out=json.loads(json.dumps(raw)); errors=[]; traces=[]
    if not isinstance(out,dict) or set(out)!={"excerpt_id","answers"}: return None,["top_level_shape"],traces
    if out["excerpt_id"]!=excerpt_id: errors.append("excerpt_id_mismatch")
    answers=out["answers"]
    if not isinstance(answers,list) or len(answers)!=3: return out,errors+["answers_count"],traces
    if [a.get("question_id") for a in answers if isinstance(a,dict)]!=list(question_ids): errors.append("fixed_question_ids_or_order")
    for ai,a in enumerate(answers):
        if not isinstance(a,dict) or set(a)!={"question_id","answer","supporting_snippets","source_unknown_caveat"}: errors.append(f"answer_{ai}_shape");continue
        if not isinstance(a["answer"],str) or not a["answer"].strip() or len(a["answer"].split())>max_words: errors.append(f"answer_{ai}_answer")
        if not isinstance(a["source_unknown_caveat"],str) or not a["source_unknown_caveat"].strip(): errors.append(f"answer_{ai}_caveat")
        snippets=a["supporting_snippets"]
        if not isinstance(snippets,list) or not 1<=len(snippets)<=2: errors.append(f"answer_{ai}_snippets");continue
        fixed=[]
        for si,s in enumerate(snippets):
            repaired,trace=repair_snippet(excerpt,s,max_snippet_chars);trace.update(answer_index=ai,snippet_index=si);traces.append(trace)
            if repaired is None: errors.append(f"answer_{ai}_snippet_{si}")
            else: fixed.append(repaired)
        a["supporting_snippets"]=fixed
    return out,errors,traces
