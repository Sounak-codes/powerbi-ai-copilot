# Parental Leave DAX Measures

```dax
Companies = DISTINCTCOUNT(parental_leave[Company])

Industries = DISTINCTCOUNT(parental_leave[Industry])

Average Paid Maternity Leave = AVERAGE(parental_leave[Paid Maternity Leave])

Average Paid Paternity Leave = AVERAGE(parental_leave[Paid Paternity Leave])

Paid Leave Gap = [Average Paid Maternity Leave] - [Average Paid Paternity Leave]
```
