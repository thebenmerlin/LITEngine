/* -------------------------------------------------------------------------- */
/*  Demo sample data — several fact patterns, each self-contained, so a       */
/*  demo can walk Precedent Search → Fact Extraction → Argument Graph →      */
/*  Simulation → What-If → Ask the case on any one of them.                  */
/*                                                                            */
/*  Every case follows the same structural template verified (against a      */
/*  live local run) to pass the backend's rule-based extractor cleanly: a    */
/*  proper caption block for clean petitioner/respondent + court-level       */
/*  detection, an explicit appellant-side signal (Section 374 for an         */
/*  accused's own appeal, Section 378 for a State appeal against acquittal)  */
/*  so appellant_type classification is unambiguous, explicit "Whether...?"  */
/*  issues, and a prayer clause for relief_sought.                           */
/* -------------------------------------------------------------------------- */

export const SAMPLE_CASES = [
  {
    id: 'ramesh-kumar-302',
    label: 'Ramesh Kumar v. State of Maharashtra (§302 IPC, accused appeal)',
    appellantType: 'accused_appeal',
    filingDate: '2021-04-12',
    precedentQuery:
      'Appeal against conviction under Section 302 IPC based solely on eyewitness testimony, with delayed FIR and unrecovered weapon corroboration — plea for culpable homicide not amounting to murder under Section 304 Part I',
    text: `IN THE BOMBAY HIGH COURT, NAGPUR BENCH
Criminal Appeal No. 482 of 2021 (under Section 374 of the Code of Criminal Procedure)

Ramesh Kumar
Versus
State of Maharashtra

CORAM: Hon'ble Mr Justice AK Sharma.

The appellant was convicted by the Sessions Court, Nagpur under Section 302 read with Section 34 of the Indian Penal Code for the murder of the deceased, Suresh Patil, on 14 March 2019, following a dispute over a land boundary between the two families. The prosecution's case rested primarily on the testimony of two eyewitnesses, PW-1 and PW-2, who claimed to have seen the appellant assault the deceased with a wooden log. No independent corroborating witness was examined at trial. The post-mortem report confirmed death due to blunt force trauma to the skull, consistent with the alleged weapon.

The FIR was lodged with a delay of eleven hours without satisfactory explanation. The recovery of the weapon under Section 27 of the Indian Evidence Act was not corroborated by an independent panch witness. The trial court failed to consider the accused's defence of grave and sudden provocation arising from the land dispute. The Sessions Court convicted the accused and sentenced him to life imprisonment under Section 302 IPC.

The following questions arise for consideration before this Court:

Whether the conviction under Section 302 IPC can be sustained solely on the testimony of interested eyewitnesses, in the absence of independent corroboration?
Whether the delay of eleven hours in lodging the FIR is fatal to the prosecution's case?
Whether the facts as proved make out an offence under Section 304 Part I IPC rather than Section 302 IPC?

The appellant respectfully prays that this Hon'ble Court set aside the conviction under Section 302 IPC and instead convict him under Section 304 Part I IPC, or in the alternative, acquit him of all charges.`,
  },
  {
    id: 'state-kerala-acquittal-376',
    label: 'State of Kerala v. Ravindran Nair (§376 IPC, State appeal against acquittal)',
    appellantType: 'state_appeal',
    filingDate: '2022-08-03',
    precedentQuery:
      'State appeal under Section 378 CrPC against acquittal in a Section 376 IPC prosecution — trial court disregarded victim testimony and medical evidence, delay in filing complaint explained by fear of social stigma',
    text: `IN THE HIGH COURT OF KERALA AT ERNAKULAM
Criminal Appeal No. 219 of 2022 (Appeal against Acquittal under Section 378 of the Code of Criminal Procedure)

State of Kerala
Versus
Ravindran Nair

CORAM: Hon'ble Ms Justice L Menon.

The respondent was tried by the Additional Sessions Court, Kochi for an offence under Section 376 of the Indian Penal Code alleged to have occurred on 2 November 2020. The trial court acquitted the respondent, holding that the delay of nineteen days in lodging the complaint created a reasonable doubt and that the victim's testimony, though consistent, could not be relied upon without independent corroboration. The medical examination report, which recorded findings consistent with the victim's account, was held by the trial court to be inconclusive.

The State, being aggrieved by the order of acquittal, has preferred this appeal under Section 378 of the Code of Criminal Procedure. The prosecution contends that the delay was satisfactorily explained by the victim's fear of social stigma and initial reluctance to approach the police, a circumstance recognised in a long line of authority as insufficient by itself to discredit an otherwise consistent and credible testimony. The prosecution further contends that the trial court erred in treating the medical evidence as inconclusive when it was, in fact, corroborative of the victim's version.

The following questions arise for consideration before this Court:

Whether the delay of nineteen days in lodging the complaint, explained by fear of social stigma, is fatal to the prosecution's case?
Whether the sole testimony of the victim, if found truthful and consistent, requires independent corroboration to sustain a conviction under Section 376 IPC?
Whether the trial court erred in disregarding medical evidence that corroborated the victim's account?

The State respectfully prays that this Hon'ble Court set aside the order of acquittal and convict the respondent under Section 376 IPC, or in the alternative, remand the matter for retrial.`,
  },
  {
    id: 'anita-desai-138-ni-act',
    label: 'Anita Desai v. State of Gujarat (§138 NI Act, accused appeal)',
    appellantType: 'accused_appeal',
    filingDate: '2023-01-20',
    precedentQuery:
      'Appeal against conviction under Section 138 of the Negotiable Instruments Act for cheque dishonour — rebuttable presumption under Section 139, defence of a blank cheque given as security not towards a legally enforceable debt',
    text: `IN THE HIGH COURT OF GUJARAT AT AHMEDABAD
Criminal Appeal No. 764 of 2022 (under Section 374 of the Code of Criminal Procedure)

Anita Desai
Versus
State of Gujarat

CORAM: Hon'ble Mr Justice PK Trivedi.

The appellant was convicted by the Judicial Magistrate First Class, Surat under Section 138 of the Negotiable Instruments Act, 1881 for the dishonour of a cheque for Rs. 8,50,000 issued in favour of the complainant, dated 6 September 2019, which was returned unpaid with the endorsement "insufficient funds". The trial court held that the statutory presumption under Section 139 of the Act in favour of the holder of the cheque had not been rebutted by the appellant.

The appellant's defence at trial was that the cheque had been handed over as security for a business arrangement that was never concluded, and did not represent a legally enforceable debt or liability at the time of presentment. The appellant further contended that the statutory notice of demand under Section 138(b) was not served at the correct address and that the fifteen-day period for payment had not validly commenced. The trial court rejected both contentions and sentenced the appellant to one year of simple imprisonment together with a fine of twice the cheque amount as compensation.

The following questions arise for consideration before this Court:

Whether the appellant has discharged the burden of rebutting the presumption under Section 139 of the Negotiable Instruments Act on a preponderance of probabilities?
Whether service of the statutory demand notice at an address other than the appellant's registered address is valid service under Section 138(b)?
Whether a cheque admittedly issued as security, absent evidence of a concluded legally enforceable debt, attracts liability under Section 138?

The appellant respectfully prays that this Hon'ble Court set aside the conviction and sentence under Section 138 of the Negotiable Instruments Act and acquit her of all charges.`,
  },
  {
    id: 'state-up-304b-acquittal',
    label: 'State of Uttar Pradesh v. Mohammed Iqbal (§304B IPC, State appeal against acquittal)',
    appellantType: 'state_appeal',
    filingDate: '2021-11-09',
    precedentQuery:
      'State appeal under Section 378 CrPC against acquittal in a dowry death prosecution under Section 304B IPC read with Section 113B of the Evidence Act — presumption of dowry death, cruelty soon before death',
    text: `IN THE ALLAHABAD HIGH COURT, LUCKNOW BENCH
Criminal Appeal No. 331 of 2021 (Appeal against Acquittal under Section 378 of the Code of Criminal Procedure)

State of Uttar Pradesh
Versus
Mohammed Iqbal

CORAM: Hon'ble Mr Justice RN Khan.

The respondent was tried by the Additional Sessions Judge, Lucknow for an offence under Section 304B read with Section 34 of the Indian Penal Code in connection with the death of his wife, Shabana, within four years of marriage, on 11 June 2018, under circumstances alleged to be otherwise than normal. The trial court acquitted the respondent, holding that the prosecution had failed to establish that cruelty or harassment in connection with a demand for dowry occurred "soon before" the death, as required to invoke the presumption under Section 113B of the Indian Evidence Act.

The State contends that the trial court misapplied the "soon before death" standard by requiring near-contemporaneous proximity, when the settled position requires only a proximate and live link, not immediacy in point of time. The prosecution relies on the testimony of the deceased's parents and brother, who deposed to a consistent pattern of demands for a motorcycle and cash continuing up to within a fortnight of the death, and on the post-mortem report, which recorded ante-mortem injuries inconsistent with the respondent's explanation of an accidental fall.

The following questions arise for consideration before this Court:

Whether the trial court applied an unduly narrow construction to the phrase "soon before her death" under Section 304B IPC?
Whether the consistent testimony of the deceased's family regarding dowry demands, corroborated by the post-mortem findings, was sufficient to raise the presumption under Section 113B of the Evidence Act?
Whether the respondent discharged the burden of rebutting that presumption once raised?

The State respectfully prays that this Hon'ble Court set aside the order of acquittal and convict the respondent under Section 304B IPC, or in the alternative, remand the matter for retrial.`,
  },
  {
    id: 'suresh-yadav-420-cheating',
    label: 'Suresh Yadav v. State of Bihar (§420 IPC, accused appeal)',
    appellantType: 'accused_appeal',
    filingDate: '2020-06-15',
    precedentQuery:
      'Appeal against conviction under Section 420 IPC for cheating in a property sale transaction — distinction between civil breach of contract and criminal cheating, dishonest inducement from the outset',
    text: `IN THE PATNA HIGH COURT
Criminal Appeal No. 158 of 2020 (under Section 374 of the Code of Criminal Procedure)

Suresh Yadav
Versus
State of Bihar

CORAM: Hon'ble Mr Justice SP Singh.

The appellant was convicted by the Sessions Court, Patna under Section 420 read with Section 406 of the Indian Penal Code for allegedly cheating the complainant of Rs. 12,00,000 collected as advance payment for the sale of a residential plot, pursuant to an agreement dated 18 January 2017, which sale was never completed. The trial court held that the appellant never intended to convey title to the property and had dishonestly induced the complainant to part with the amount.

The appellant's defence is that the transaction was a bona fide agreement to sell that could not be completed on account of a subsequent title dispute involving a third party, a purely civil contingency, and that no dishonest intention existed at the time the agreement was entered into. The appellant contends that the dispute is, at highest, a civil breach of contract actionable in a suit for recovery, and that the essential ingredient of Section 420 IPC — dishonest inducement from the very inception of the transaction — was never established by the prosecution. The trial court rejected this defence and sentenced the appellant to three years of rigorous imprisonment.

The following questions arise for consideration before this Court:

Whether the prosecution established dishonest intention on the part of the appellant at the time the agreement to sell was executed, as distinct from a subsequent failure to perform?
Whether a dispute arising from an unforeseen title defect is capable of sustaining a conviction under Section 420 IPC, or whether it is confined to civil remedies?
Whether the ingredients of criminal breach of trust under Section 406 IPC are independently made out on the facts as proved?

The appellant respectfully prays that this Hon'ble Court set aside the conviction and sentence under Sections 420 and 406 IPC and acquit him of all charges.`,
  },
  {
    id: 'priya-nair-498a-cruelty',
    label: 'Priya Nair v. State of Tamil Nadu (§498A IPC, accused appeal)',
    appellantType: 'accused_appeal',
    filingDate: '2022-03-28',
    precedentQuery:
      'Appeal against conviction under Section 498A IPC for cruelty by in-laws — general and omnibus allegations against extended family, absence of specific instances or proximate link to the complainant',
    text: `IN THE MADRAS HIGH COURT
Criminal Appeal No. 97 of 2022 (under Section 374 of the Code of Criminal Procedure)

Priya Nair
Versus
State of Tamil Nadu

CORAM: Hon'ble Mr Justice V Krishnan.

The appellant, the sister-in-law of the complainant, was convicted by the Metropolitan Magistrate, Chennai under Section 498A of the Indian Penal Code for subjecting the complainant to cruelty in connection with demands for dowry, along with the complainant's husband and mother-in-law, during the period 2018 to 2020. The trial court relied on the complainant's testimony that the appellant, who resided separately and visited only occasionally, had made taunting remarks about the dowry brought by the complainant on two or three such visits.

The appellant's defence is that the allegations against her are general, omnibus, and unsupported by any specific instance with date, time, or particular words attributed to her, and that she did not reside with the complainant at any point during the relevant period. The appellant contends that the settled position requires courts to be cautious against the misuse of Section 498A to rope in distantly-placed relatives on vague and undifferentiated allegations, and that no case of cruelty specific to her was made out. The trial court nonetheless convicted the appellant and sentenced her to one year of imprisonment with a fine.

The following questions arise for consideration before this Court:

Whether general and omnibus allegations, without specific instances attributable to the appellant, are sufficient to sustain a conviction under Section 498A IPC?
Whether the appellant's non-residence with the complainant during the relevant period is material to the question of cruelty within the meaning of Section 498A?
Whether the trial court failed to separately assess the evidence against the appellant as distinct from the evidence against the complainant's husband and mother-in-law?

The appellant respectfully prays that this Hon'ble Court set aside the conviction and sentence under Section 498A IPC and acquit her of all charges.`,
  },
]

// Back-compat aliases — first sample case, used before this became a list.
export const SAMPLE_CASE_TEXT = SAMPLE_CASES[0].text
export const SAMPLE_PRECEDENT_QUERY = SAMPLE_CASES[0].precedentQuery
export const SAMPLE_CASE_LABEL = `Sample: ${SAMPLE_CASES[0].label}`
