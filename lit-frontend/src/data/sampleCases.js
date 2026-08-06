/* -------------------------------------------------------------------------- */
/*  Demo sample data — one consistent fact pattern reused across pages so a   */
/*  demo can walk Precedent Search → Fact Extraction → Argument Graph →      */
/*  Simulation → What-If on the same underlying case.                        */
/*                                                                            */
/*  Written to actually pass the backend's rule-based extractor cleanly      */
/*  (verified against a live local run): a proper caption block for clean    */
/*  petitioner/respondent + court-level detection, explicit "Whether...?"    */
/*  issues, and a prayer clause for relief_sought — every field on           */
/*  StructuredCaseProfile comes back populated, so Fact Extraction, the      */
/*  Argument Graph (20+ connected nodes, zero isolated), Simulation, and     */
/*  What-If all have real structure to work with instead of empty fields.    */
/* -------------------------------------------------------------------------- */

export const SAMPLE_CASE_TEXT = `IN THE BOMBAY HIGH COURT, NAGPUR BENCH
Criminal Appeal No. 482 of 2021

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

The appellant respectfully prays that this Hon'ble Court set aside the conviction under Section 302 IPC and instead convict him under Section 304 Part I IPC, or in the alternative, acquit him of all charges.`

export const SAMPLE_PRECEDENT_QUERY =
  'Appeal against conviction under Section 302 IPC based solely on eyewitness testimony, with delayed FIR and unrecovered weapon corroboration — plea for culpable homicide not amounting to murder under Section 304 Part I'

export const SAMPLE_CASE_LABEL = 'Sample: Ramesh Kumar v. State of Maharashtra (§302 IPC appeal)'
