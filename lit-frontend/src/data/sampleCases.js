/* -------------------------------------------------------------------------- */
/*  Demo sample data — one consistent fact pattern reused across pages so a   */
/*  demo can walk Precedent Search → Fact Extraction → Argument Graph →      */
/*  Simulation → What-If on the same underlying case.                        */
/* -------------------------------------------------------------------------- */

export const SAMPLE_CASE_TEXT = `On the night of 14 March 2019, the appellant, Ramesh Kumar, was tried by the Sessions Court, Nagpur, along with two co-accused for the murder of Suresh Patil under Section 302 read with Section 34 of the Indian Penal Code. The prosecution's case rested primarily on the testimony of two eyewitnesses, PW-1 and PW-2, who claimed to have seen the appellant assault the deceased with a wooden log following a dispute over a land boundary. No independent corroborating witness was examined. The post-mortem report [Ex. P-12] confirmed death due to blunt-force trauma to the skull, consistent with the alleged weapon.

The appellant's counsel argued that the FIR was lodged with a delay of eleven hours without satisfactory explanation, that the recovery of the weapon under Section 27 of the Indian Evidence Act was not corroborated by an independent panch witness, and that the trial court failed to consider the defence of grave and sudden provocation arising from the land dispute. The Sessions Court convicted the appellant and sentenced him to life imprisonment under Section 302 IPC.

The appellant has preferred this appeal before the High Court challenging the conviction, contending that the prosecution failed to prove its case beyond reasonable doubt and that, at best, the offence would fall under Section 304 Part I IPC (culpable homicide not amounting to murder) rather than Section 302 IPC.`

export const SAMPLE_PRECEDENT_QUERY =
  'Appeal against conviction under Section 302 IPC based solely on eyewitness testimony, with delayed FIR and unrecovered weapon corroboration — plea for culpable homicide not amounting to murder under Section 304 Part I'

export const SAMPLE_CASE_LABEL = 'Sample: State v. Ramesh Kumar (§302 IPC appeal)'
