#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_termsub_7_2010.sh — إنهاء البند المؤجَّل من دفعة العدد 1809:
# الاستبدال اللفظي الشامل الذي أمرت به الفقرة الثانية من المادة الأولى من
# المرسوم بقانون 91/2026 («الوزير المختص» و«المحكمة المختصة» بدل «وزير التجارة
# والصناعة» و«محكمة أسواق المال» أينما وردتا في القانون 7/2010).
#
#   • قياسٌ شاملٌ أولًا (TERM_BLAST_RADIUS بسياق كل ورود وفئته) قبل أي كتابة.
#   • ولا يُستبدل إلا الورود **الحرفي** في **مواد المتن النافذة** — أما المواد
#     الملغاة (108-113 و116) ومواد الإصدار والديباجة والمذكرة والصيغ التي لم
#     يسمِّها المرسوم («محكمة سوق المال») فتُعرض في التقرير ولا تُمسّ.
#   • كل الكتابات في معاملة واحدة، والنص القديم كاملًا إلى previous_versions[]،
#     وإعادة التشغيل بلا أثر (منع التكرار ببصمة sha256).
#   • فهرسة **تفاضلية** لما تغيّر وحده (لا فهرسة كاملة أبدًا — قاعدة §10).
#
# النجاح النهائي = DONE_TERMSUB
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# لا يُعتمد على $0 أبدًا (درس §13): عند اللصق يكون «bash» لا مسار ملف.
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_termsub_$(date +%s).log
  echo "running in background (survives terminal disconnect). log: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "follow with:  tail -f $LOG"
  exit 0
fi
[ "${1:-}" = "--worker" ] || echo "(pasted mode: running in the foreground)"

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a
mkdir -p /opt/LegalMind/tools /opt/legalmind-data

echo "═══ 1) كتابة السكربت ═══"
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/apply_term_substitution_7_2010.py
H4sIAAAAAAACA61bbVMbV5b+rl9x01kq3Vhqg7OTxKplqrCtJN5gcAHe2SzRNo3UoE6kFqVuYZis
qwI2mDB5mexO1Vbt7IdNPLZBNiHEsR2Sb8yfkL7ml+w557707VZLOC8kYKn79r3nPOf93Nsvs8Jo
gVWaVT9YKbJ2tFx4A6/kDMPIdR/27nQfdp90O9397hF+Y/gH/tvsft/boy/d7+DvtrjT/Qav3utt
d4+7Hdbd793lD2z2tuDKAR/zCP7u9PbgKzy3wwdswzJHcsC93i5c+jhx+7j7BK5u52DOLXp+F+8d
97Z628y8OG4xeO5JbwemuDB24TVm0mO3YdQeEoJf9vB51j0Zf2PsYvcTGnb+4vkLY1Yxl2Pwc/qo
twuMCmaRoRP48BA56T5kBs2x2/0WJjyWRH0Nt54arLcrbm93D2HNbcGHHNA9MGA9mEvNByAZiblg
2GO6dUCkwIx09Skw9BAeO+Br6PPfQzxg0JbCr3fHQOj3ABv4hlMcA6RIO8DPZZUB3esJ5MbH+Ppi
zu+QJta9T+jdtU9/zOV6d7vfwJRE3j48dcR6t3FSNjoK4toCjp70/kTLw/N/6z7ufdb7Ah7HSyS6
Y5xydFTQdASKdCLFfgLkHjEUDzNPH46/ahWFKvU+Z0kt7H2aA1iPYbHD3ieMBL0DqoaUwLBDPjkQ
97T3ae8LVKPd7iMiZIsL9Rj/+Y5oEcqBTz4gtDsgK6Dqee9zlBhqBc6zyYD251JaCOIml9jpj4y0
dTsHEH0OQ/blQl8RasC4zRA0YQqACAxHlju9z5FqRBaVA+bsPiMFec4hBZuyczkuCRzYfcx++ugv
jDAGNoFxaXr4kdsMrIaq9ggVvUPE7MF4uPIMPgBVRRCvicayzXG6DWqu884W696KHxZeL6AuFEYW
UWh3SN6E/yMa9iVChLbyFO0YsaF5QOHg9wgf2ew+AP7u8nHPiasTqdvI+RYJ7xhFswmzkI4gCE+Q
NwAvOaF5evzaGOsewtdNZNFCZdtCykjhkQNQc3j8YHTURg4vkFKDEqJINIO+z69uc4YeAyHbIGLU
FpQBKsRzlENREAqk3itI3eSmewBLC0JItqjJt/mET4CZL2DwXWEesdNiJsdwny49RK0npaFrwP5e
9wdu0l/DxB9b3b/G6+8XhC+QUiI7484SVR/EAQh+w7+gu4SbHek1lbUDlWZSso3pxe4nahn44bfr
buQ3A8dtRX6l7i2S/FCNEURuR8QQULsYtle9VuhVveqiRaC/auFgEhzhgeYM/3yDtCPVUiCoe70v
ELhdks8RMP0ZKLfyUpp+EOoI7F1G/Bxzh6Q8Xu92LKsCioZbyy4CJIbBfD/A1wPEYHzsjcL4+Kuw
8vj4a12yGrpLMtM8myY6svQnZKICd9BrDTgV0fDvAbgschc03zYw9xj+gnYjNSfcW94B9fleurz7
gjphUfdh+q8pzMJaT8EHwWAGenoEYBwJPeUoAk3dI52M7/AOp066Z7QJhPFrirXkO3alXpB04ngM
OHe6B0WmC+kQIzAwQ55P6itJ7BAIQqYeMQ5v72M7IYWEBICpp6gJaO08qiE3+2R/B5KibVCT23GG
cB9GPIMRh0j56CjSJXTw9FFSs8H9yrwjKZQdChCbKniJUML6Uxqu5DtwaV+ip57hToKQFdjsgD+9
Y/cpHbdiqTyoUnvIDiodRBAtbqNW6TFbMECAHZNMMCSKiMnj2Pb4+D9SPAWltYoamzgHo4i73fsz
uNB+z8NjWTJ20qgOmfIerITxU8OGov4xCPeEM4zeBMnofoPL3bUzzA2dJk/LRDQF/LYJ5QdcfuD/
NjHfABOD0d92D86j4aET3CTdQtNIu1kxtXCqZFkYMeHe04TiYxyCyydw45lyqp2k248jMY+nEA23
SUWAYMSzwOONcLM8lCAvAn6YnMKsUFdU/+5B96889gDjuzz24LKbYId3MPQeg+Kc8LCu25uIFTxl
ghXMxdmZqanSFefS5OV3uB/lAYcMTzwM9oJyFjkBT6XuU4K82PAit+pGrr3a8tb8Zjt01sApgwsP
F8oYuym8oN6FNffC715jJPUdaZkdpAomv0N4cgeBQQTk8bn0xLelz93nKZ+YTwYvkbeBjEjT7iNW
sWfpgC79gAuoNOIeeJtjweYhifoJOhkMu1tFJlLAREbSjyBXYZEAAEeYWB+hHTzu7qNQdvBzR2ql
DL7oW5GVx0pLDsFrbFoiDNI8gjf04Lvo+FQwA8XdZeiaUbBSNx+TnzvRlJV8Bea0EqAO/PcDuoIU
y0mTLPIUNk7FuJvtgNfYQmdxTwZ0qRQqJEwMUBYhmaTh7+E0Wu4Sc06YcROl554jRDxJfAgfP2VU
84EXo6JjXxRmXFjCe1GmRgIjPSLuYT4Ozwk8gEnrlxwGMqljckwdkSwQTKBFxzwvRivcl/bHXQXS
vwnwomdD+S+2PD+oeutO1aujAWwsIicYmvAuF7p8gPRGGrEls+odyuAPAcTF+dLstbkbl5yZdxah
dIRcOr40PTNzfRENbkf5W9Cq3mcqPe19wt0CaV8f6rAaVtI5v7HabEUs3AjzrAm/LS/Pam5Yq/tL
zA2ZU8szMGQv8hteLgej7FU3qtl+EHqtyBzLM+N8czU6P+WtuPVrwLdh5ZqhXalV/ZbZf0uuthpu
VJqrK7nlVrMhv9jRxqoX2u+HzYCJYf8Mn5f4IC9Y8QPPDpqthlv3/+i17IobNAO/4tblaHXPibz1
KJebmvyDc3229ObVfwUkjUSWaeSuTs/Nz964Vpqej29eHC9g8V3ww7DtFcb1Qc7U5KXSFAw1DS0H
y6r5L46nKn5Uu1/RazD0ZFj9GGYmyRZg/Nbkv5Xm50vOlcn5EvJG98cuwjgjd/ntyem3wKtfvTLn
vHl1iu6TkOoopAYIqYBe+3zktRphe8l53UG4nErNDVa8quNXQztaj0BrXk6GxQ5V2n0FhyhoEnmr
buixSZJf+ZbnZic8ycGHc6Doc0DkAoFgDupN9Lcl8sP6IlZeTndW3yJ/Vv8EpioTGjzNGpItpdoc
vDfQl9RnJE6kPyrDyE4lcjempyevgWD/ZXL26uT0PGFmDEvvDCA7V/WWmYNm44D91JpmKLI4cAyy
SsdkQcuauMO9DdmESpJMkTyBzxTpE/+I6cqXjJjbp2L74Lxw3DTASgpfeFbemfsO1v3SRveE1ITA
TMuzQR/NlrHQ+6j3p0LvP8soG/gNLTUmtFveat2teKbRvcdFZ1jatfsZ176S1zJnIT3q3dWf6H1M
1/YSs/yNru0mrj2Q42jmlhe1W0HMxnvhObzPiAM7jFr+qmlJiay2w5qDiZOJaRS45XqVXFoeXFzk
xTLCYoTaHANiLc/FMjIwkTtwZSM9hAvPUDKiHyZSjg4K4wm5LkxSlUBqLgDl1GyevJmSPtsLKs0q
ME/NWsOy7Jq3XvVXvDAyOQxICzxa9+EK8maveJFp9FFoWKzZYgtl/pC/zNxgw1xd46P5ojBkYoIo
WYahq2vMD2h2rQ4RmHMM33TroadosN3VVS+omh+qwQYyYBRjrOM7YsEirqZfVn0GpxnAXd3vZg9b
2oBhKELtttuq1Pw1uOni6jLS2upD0Lxpqi/4549NCIPtqGLZfthcxpAH4PIJb3G8kOGFDFDLgDxe
zfWBM99qe0L5KnU3DP3lDbPpV0HzMCbn2VoYuVFb8w7URztIdCi5Od9FFxFnOyJX3xOtte5xMd36
kj2ue1wXVcF0J26rKL0DRTAFKagfBtcBDWGjT/hG3GdRcxiFhtdoFgxUGeAy6xlZ9atnCAhaTW9H
AZpuY6nuGUgOTAUGUA1v+lHNNArqXr9GGnqn4YwlMLD7wYrsfNFKBg/3wxjI7HOcsZRawg2q6KlA
syo18FX/nmzQvVc99w/gtmBhKxM6nsPEDUAjl2BdNBMhh8hNXr8+9a5zeWpyDuNV9rNCK5sBGqXT
XDa5I1yttdwQNPOmX41qE6+NaarJayMC4BlGr1T5rnq5cXBNtvYoGqHq3dNSk6e8s0R9evKqWukg
1bPZjjDslrmPjABO+Mr3LW7W/LpHZhZD5sNd8prLkHaZkiF6zooHLcO4f2JjxUQWuAS69YG6gs64
4a5jMu5DEUOQxDMs4V0/gHwxIOwsHHWO4Ve+pgXfUs+EgQ/+MdLjrhawcJYFt7hUjgOXfBAgkK7V
NH766IFBzpv9no0xD/wvmew5Nf05Fg9aAi4ViWqwRpLAM0W7rluwuFCXEGoDs9JuaVohNidYvCso
C/9En95m1HvCEtbE3RXImjadZOqG7dlUaemIvAq3HVBLNrGYk2oBdNjeuldpR54Z+33DmCtNlS7P
M3KzS+97lcgRztZr+ctQ15BNcm8HI1o+1D9uXeQBsr2ia8WbszPX2AcQL+pedcVz+Jwh+8PbpdkS
rMKmrr5TYiMhm5m9Uppll96Fa0BFHIpMrV46x4wRIy/gbzVvYmKEfCx74BLcet1UkRnCGQ3QXIHr
g/DmNsLIa5TWfYjYOPG1q3NzV6ffkp3cRCOlA/Gig6SRNWLhswUQipad2ImzDTbCYgotvjVa86OQ
bC6G4WVtv0eUGhRN9E3OOPGWbTy6SFOuuS3fDSJHmzpO78/sa3JHgMm0k6DtZaa1Iw9YshEpMmnO
0jIPJenYy82OSx79fhJzvCfcCY+M6k6lTrIbFtXV2EBMo5cEZI9qBBFXhykC7yZSgeVZ0jUF0qtV
mu0gwtTQStxHlSn2lbSIlcrJDFDMIsfAAPLhM/yFzzAXT9DgM6yPuZR3M59ZHsd1MmZmAU4UreNE
6TiC9N1KUjhcVMJtJIcIPYOPE2xwR3lPNOlR7THGHQqNU9AR7jBFoAGoywKJ7UeTP/X7LFhjRfwZ
4A4HVIeVr1xgwa2khlAynq5Ih6rJ2osoiW6ZZ/LD4wN8XctLJXgRxthATVlDPREFhA8kG9iHcy5B
8jLvzE5euXpjLu70qGCjH0MxZb2lal0qc/n5iyOraFj67Cy72Sy6B6+fx1wMMBypol/EgIgOQWjH
0obDzf7DW8ql1FAmiFyMKx9mh14EMdNt1yPTrC2QIpTzDD4hnGVIFxYgsRgrW6nnFrIGlxfGyuzc
BBt/scHjNBguBEZZBhT+QEylwOO9gGW1nNJunPehVL8l7qyQbPiuB9UuEm6Jj0l+BVYGhs0AgicW
25WKhbCFYEde1RR4+RDXQtOykgracFsfYBL7086fU70ZSm9IHhNMz3h5joPjVUOH70BD5tHJLISs
ZC9QaQoeERoJT39k59lIYfxCyIqgF0p/xNkLvCIbw1jkQ7xF1VF8I7+S6zyxI7QJ6fw14ihi9Nzk
u6w8Lmf2w2j7xDaEjQFkSWXV1+3Q2Yw92pdInu+Ic/u0fGuaIHHmPPvA25ioQ4lWddl6kZnrQi3z
DD6BUymnJazBvTASlmW+IqD/+39zUzRrap4an4c+xLof4MyJiZG8CpnnAjmf8kLx1XK/+9PWxx8u
vkqMl+4es3HL6FH+2sZkRi8yjfyahrxOY1oCEvZfhPqaQn1Nog4fRBDgX4YAv6aAv/ALgI+jbCbs
P/3P/7H0XnQypxi0C/1C28+DxKDtLqcl0tQkEhP/q+Qhqud9uZ+Rlk9Tyacp5dNUVtHUhSM7pRDO
8uQDRE0HAb++4UAxGmJll6cBWrs640DoiTyrqZ+6iQ8hqSaD1rDSyj8S1QO95x9vDWptLbk92O3E
BR/fLYl7Ab8opffP6MWxlxLhJCklzF78oO3Fhbloaw4oEjAJo4QBxsU9UC2HjzN/R+b9t3RSsQzE
Ji2fyV5z622vP0gqsuKSw7sp6ZKrqnu0f6paKNTpAB3wdWRfrCZBKImuBRiXYeAaEfKjauTLma2+
pzh5kL9oc7NRRo0WfAASY/zYn7RrnMRpLG5yquomaoriBrJRnJzyUbWIzEN5sTJk6z57qzvuefHd
9MS+fbyXjoczVeufnwK7x6PFDtY7aDyMji5viQ0IWanraiGwcHhXBzRWICIunOMgJiXS3z9Aic47
U6Vp7CJcm5y//HZRdQuSfJB97yLLIt/h+R7tKMIV2xheA6CjQlPLpDKf5MbKqIqdgfoHt/GefLpf
BwdxPVuau3rlRqmYCnyUym6JipSOmfR7QNtQDCWVEO1VqXxseC8mhukZvomsKJIHStAR0lbrMXzc
RvAf82xPpGdEDnaNY+0lzzfB/wEMP7yVuAN4utUqmfuQLbH0Hr2VmGPBcBtgYHzzBTdA4uFZ4+A3
cnC7hcbqOzoDR4eV5iofbibwM1LhKH43YV8/1fabvYCQPIxwcfw8HT5IKrxhnj7KPIl/+qPMI2SJ
yiuReB3aXcSFPk7l/QO7adxnJE4HPREnn1JUJU6QUU7at3llG2m54hEFSgciP2pjr5RkIPxqrGJ6
9xUC9I3rdCyir006yC/MleaTvdeJEaqUxEmTanxNtmTpS3sVlQg39SZwA88aNL1szsJDiV6s/qNc
Tj51wiX2RXl+UoZsw+JbM/GSIh2RoYYssC+bE4eKlFGL4jBBEG+ygFgN+/2mH5gG90UqxwOhUBSD
jA4+8sBV5pkD5TdCNlYy0RPkiSxv2YcvLSLLabaj0K96PN3z1iv1dtXDIyha1vebnoyjeCKj6emj
tC3Ids1XuIF1+qO+K6kRVxykeaLd36j+zsRdE9zSW1kxU339V/7jFb0/bw1UnKHN/umZeWb66Dcn
p981R0LLQuWCzAS33XUg85klfoLwX0b2APqShyHUhkIz8ExrYUydSLnZ8iNPHjoyY4njzioDbxuY
6XNMoJc3gUM6fwA0TsgTCHiCbbkWs7Zcs2lyrMyEFuP0tBMFV2i7rRpq20+cooYLAwUR1RB7l83Q
9oI1v9UMFgzwKJOXJudKzo3ZKdHH6isBotZGTAXxIU+9QU4cADYmzEvk4vdkJKbheNkGxKBsM/m4
dqs/i8gSHU/iR8+Qif4TNSMQ7ZIHluvpGz+xnAaUyD/95SP1f7ITqt/JWDGu9vAEjty9618nclsr
Ht9WaWGrEX1LS9ZOw3I7vZrCJ6F+XBinvxfKVqozN2we3BrHOgcmebUsDiEML5Osct98y6sxuAMd
nmA1AwRRbokBxUxyX+aeC/sK+ELED+qdE0zWj3hlS60BcYyV3tKBTOBrvllBYV87JC0DN51lPpHJ
tjrEOoAEUSZjzfyMXpTAo+hUiGjVuX7iljLJE3qPbYuOKvMdtv2M19TszDVTrmOhnO1AVXdGP0sr
tybTu4f6Cw9nthIwhgwrMoyBb3swEY12seJCZOLzg/QSjDgRTwhirwWGfcZfwuBHxNUbO8PXT/KA
fdQ7sgP4jDekbJ4FasedeeGnMnyUlW28ILIz7wwYyYPAQFfyXtDnTFJ4mT+rs2Od5YJil53Zacpl
WbG7DFnoCxlxhg2r56EsVh4h25ozarHLM9dLzqXZ0iQWwyr9+Vn5jt68OlNxEzrc4S8s8FcU0V72
XspC9DcJRui50wEIIdOD1IuidnnmBpSJInl4obc6tPP//BzumZzzQN1sNHx56BEyLm810gjJaBNr
b9sU9Vd3+Is76uWFM+1SHU9KsKFbK6GS2MhMm5p6vSNuLMQHZLLM6Mx8Jn9G+iIapBgyhRmm+oaZ
qfSAMzEDVGuYbqfKMN40SSXfuEJfMtS3nTCsDUT5Q4jvTVA7CGM4jIN5jZGw2N/YeSnZvsllTIMN
qcZZZ2jZ7yfYuFgkuxxXlQ4IfrP7/UuiUZPd98cC8X//i5l9C06MVC0j0UJrZJ5Cxfovl0wSBrwZ
qyk8L8GECQr1FC/ai7QBXT63zmdnlGBn+KCzanV1kGpy+krWYa2JV+IDqa8MruoHnbZKngGQwIgN
fwWWfNtZvE8VB38zhZmlDgn0eVEhhlTOJP5NH0YY9maUCZKnDKko+wYofTlRnqWrNcvKDc4Vcjnw
+I4TuA3PceiMquNg/eU44nQvL8Zy/w+UFnaKH0QAAA==
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/apply_term_substitution_7_2010.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية لكل كائنات القانون 7/2010 ═══"
BK=/opt/legalmind-data/backup_termsub_7_2010_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'legis-7-2010-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) القياس ثم الاستبدال الضيّق ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/apply_term_substitution_7_2010.py

echo
echo "═══ 4) فهرسة تفاضلية لما تغيّر وحده ═══"
IDS=/opt/legalmind-data/termsub_7_2010_changed_ids.txt
if [ -s "$IDS" ]; then
  echo "معرفات ستُفهرس: $(wc -l < "$IDS")"
  # كل معرّف يُمرَّر نمطًا حرفيًا (بلا %) فلا يُصاب غيره
  mapfile -t CHANGED < "$IDS"
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py "${CHANGED[@]}"
else
  echo "REINDEX_SKIPPED: لا كائن تغيّر — لا شيء يُفهرس."
fi

echo
echo "═══ 5) اتساق العدّادين ═══"
PG=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM knowledge_objects;")
QD=$(curl -s http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1 \
     | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])")
echo "PG=$PG  Qdrant=$QD"
if [ "$PG" = "$QD" ]; then echo "CONSISTENT_OK"; else
  echo "COUNT_MISMATCH — يُنظر فيه يدويًا (لا فهرسة كاملة آلية أبدًا)"; fi

echo
echo "═══ 6) تشخيص: صورة القانون بعد الجولة (لا بوابة) ═══"
# معزول عن set -e — درس §13: مِشجب تشخيصي أسقط بوابةً حقيقية مرة واحدة، لا مرتين.
set +e
psql "$DATABASE_URL" -At -c "
  SELECT 'كائنات 7/2010 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-7-2010-%'
  UNION ALL SELECT 'منها موسومة بالإلغاء = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND verification_status='superseded'
  UNION ALL SELECT 'تحمل «وزير التجارة والصناعة» = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%وزير التجارة والصناعة%'
  UNION ALL SELECT 'تحمل «محكمة أسواق المال» = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%محكمة أسواق المال%'
  UNION ALL SELECT 'تحمل «محكمة سوق المال» (صيغة لم يسمِّها المرسوم) = '||count(*)
      FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%محكمة سوق المال%';"
[ $? -eq 0 ] || echo "DIAG_ERROR — تشخيص فقط، لا يوقف الدفعة"
set -e

echo
echo "═══ 7) بطارية القياس (صمّام الانتكاس) ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_termsub.log 2>&1
set -e
tail -20 /tmp/battery_termsub.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_termsub.log; then
  echo "DONE_TERMSUB"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص"
  echo "  (بروتوكول عدم تصديق الفشل المفرد):"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
