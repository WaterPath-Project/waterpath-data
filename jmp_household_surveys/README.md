**Manual editing**

* Fixed headings in jmp_sanitation_surveys.csv
* Removed Western Sahara and Holy See records from jmp_sanitation_surveys.csv
* Ran transform.py for three available contexts (Urban, Rural, National)

**Issues** 

* containerBased_urb/rur — always NaN because no JMP survey maps to this bucket; it should be 0.
* missing for ~half the countries (set to 0 as a safe default for model consumption)