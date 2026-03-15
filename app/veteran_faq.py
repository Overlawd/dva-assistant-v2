"""
veteran_faq.py — Common veteran questions for improved RAG responses

This module provides the top 50 most common veteran questions to improve
semantic search relevance and can be used to seed conversation memory.
"""

import json
from typing import List, Dict

COMMON_VETERAN_QUESTIONS = [
    # Eligibility & Entitlements
    "Am I eligible for DVA benefits if I served in the ADF?",
    "What counts as 'service' for DVA eligibility?",
    "Do I need to have served a certain number of days to qualify?",
    "Can reservists access DVA services?",
    "What if I served in a war, conflict, or peacekeeping operation?",
    
    # Veteran Card & Identification
    "How do I apply for a DVA Veteran Card?",
    "What is the difference between a White Card and a Gold Card?",
    "Can I get a digital version of my Veteran Card?",
    "How do I add my Veteran Card to my myGov wallet?",
    "Do I need a Veteran Card to access DVA healthcare?",
    
    # Healthcare & Medical Treatment
    "What medical treatments are covered by DVA?",
    "How do I know if DVA will pay for my treatment?",
    "What is Non-Liability Health Care (NLHC)?",
    "Can I get mental health treatment without a claim?",
    "What is Provisional Access to Medical Treatment (PAMT)?",
    "How do I get a Veteran Health Check?",
    "Is the Annual Veteran Health Check free?",
    "Can I get a health check if I don't have a Veteran Card?",
    
    # Claims & Compensation
    "How do I start a DVA compensation claim?",
    "What conditions are eligible for service connection?",
    "How long does it take to process a claim?",
    "Can I claim for a condition that developed years after service?",
    "What if DVA refuses my claim?",
    "How do I appeal a DVA decision?",
    "What is a Permanent Impairment Assessment?",
    "How do I get help with filling out my claim?",
    
    # Financial Support & Pensions
    "What pensions are available through DVA?",
    "How do I apply for a service pension?",
    "What is the Disability Pension?",
    "Can I get a carer's pension if I care for a veteran?",
    "What is the Carer Payment and how does it work?",
    
    # Aged Care & Home Support
    "Can I access aged care through DVA?",
    "How do I apply for Veterans' Home Care?",
    "What is the Coordinated Veterans' Care (CVC) Program?",
    "Can war widows join the CVC Program?",
    "Are there special aged care grants for veterans?",
    
    # Support Services & Mental Health
    "What is Open Arms?",
    "How do I access free counselling for PTSD or mental health issues?",
    "Are there support groups for veterans?",
    "Can I get help with family or relationship issues?",
    "What services are available for veterans with substance use issues?",
    
    # Transport & Travel
    "Can DVA pay for my transport to medical appointments?",
    "How do I book a taxi through DVA?",
    "What if I need to travel interstate for treatment?",
    "Can DVA cover flights for medical treatment?",
    
    # Home & Housing
    "What is Defence Service Home Insurance?",
    "Can I get a home loan through DVA?",
    "What is the Defence Service Home Lending program?",
    "Are there grants for home modifications?",
    
    # Veteran Identity & Community
    "How can I stay connected with the veteran community?",
    "Are there events like Anzac Day commemorations for veterans?",
    "Can I volunteer or work with veteran organisations?",
    "How do I find my local ex-service organisation?",
    
    # Digital Services & MyService
    "How do I create a MyService account?",
    "What can I do in MyService?",
    "How do I check my accepted conditions online?",
    "Can I view my claim status in MyService?",
    "What should I do if my digital card isn't showing up?",
    
    # Other Key Questions
    "Can I get help with job hunting after leaving the ADF?",
    "Are there programs to help with education or training?",
    "Can I get an assistance dog through DVA?",
    "What if I'm not sure whether my condition is service-related?",
    "How do I get help from a DVA claims expert?",
]


CATEGORY_KEYWORDS = {
    "Eligibility & Entitlements": ["eligible", "eligibility", "service", "served", "qualify", "reservist", "war", "conflict"],
    "Veteran Card": ["card", "white card", "gold card", "digital", "mygov", "wallet"],
    "Healthcare": ["treatment", "health", "medical", "mental health", "ptsd", "health check", "nlhc", "pamt"],
    "Claims": ["claim", "compensation", "conditions", "appeal", "process", "assessment"],
    "Financial": ["pension", "financial", "carer", "payment"],
    "Aged Care": ["aged care", "home care", "cvc", "coordinated"],
    "Mental Health": ["open arms", "counselling", "ptsd", "mental", "support group", "substance"],
    "Transport": ["transport", "travel", "taxi", "flight", "interstate"],
    "Home & Housing": ["home", "housing", "loan", "insurance", "modifications"],
    "Community": ["community", "anzac", "volunteer", "ex-service"],
    "Digital Services": ["myservice", "digital", "account", "online", "claim status"],
    "Other": [],
}


def get_question_categories() -> Dict[str, List[str]]:
    """Group questions by category."""
    categorized = {cat: [] for cat in CATEGORY_KEYWORDS}
    
    for question in COMMON_VETERAN_QUESTIONS:
        q_lower = question.lower()
        assigned = False
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                categorized[category].append(question)
                assigned = True
                break
        
        if not assigned:
            categorized["Other"].append(question)
    
    return {k: v for k, v in categorized.items() if v}


def get_faq_json() -> str:
    """Return FAQ as JSON for database seeding."""
    return json.dumps([
        {"question": q, "category": cat}
        for cat, qs in get_question_categories().items()
        for q in qs
    ], indent=2)


def get_all_questions() -> List[str]:
    """Return all common questions."""
    return COMMON_VETERAN_QUESTIONS


def get_random_questions(n: int = 5) -> List[str]:
    """Get n random questions for testing."""
    import random
    return random.sample(COMMON_VETERAN_QUESTIONS, min(n, len(COMMON_VETERAN_QUESTIONS)))


if __name__ == "__main__":
    print("=== DVA Common Veteran Questions ===\n")
    
    by_category = get_question_categories()
    
    for category, questions in by_category.items():
        print(f"\n## {category} ({len(questions)} questions)")
        for q in questions:
            print(f"  • {q}")
