---
title: false
permalink: /
author_profile: true
redirect_from:
  - /about/
  - /about.html
---

{% assign cv = site.data.cv %}
<h1 class="page__title">{{ cv.basics.name | escape }}</h1>

{% assign current_work = nil %}
{% for position in cv.work %}
  {% if position.endDate == nil or position.endDate == empty or position.endDate == 'present' or position.endDate == 'Present' %}
    {% assign current_work = position %}
    {% break %}
  {% endif %}
{% endfor %}

{% if current_work or cv.profile.industrySummary %}
<h2>Position</h2>
<p{% if current_work %} data-cv-id="{{ current_work.id | escape }}"{% endif %}>{% if current_work %}{% assign position_initial = current_work.position | slice: 0 | downcase %}I am {% if 'aeiou' contains position_initial %}an{% else %}a{% endif %} {{ current_work.position | escape }}{% if cv.profile.researchArea %} in {{ cv.profile.researchArea | escape }}{% endif %} at {% include cv/link.html text=current_work.organization url=current_work.url %}{% if current_work.organizationShort %} ({{ current_work.organizationShort | escape }}){% endif %}.{% endif %} {{ cv.profile.industrySummary | escape }}</p>
{% endif %}

{% if cv.profile.researchInterests %}
<h2>Research Interests</h2>
<p>{{ cv.profile.researchInterests | escape }}</p>
{% endif %}

{% if cv.education.size > 0 %}
<h2>Education</h2>
{% include cv/education.html narrative=true %}
{% endif %}

{% assign homepage_awards = cv.awards | where: 'homepage', true %}
{% if homepage_awards.size > 0 %}
<h2>Honours</h2>
{% include cv/awards.html records=homepage_awards %}
{% endif %}
