select
  PVV.PersVV_ID,
  Pers.Person_Id,
  Pers.Name,
  Pers.Vorname,
  Pers.EMail,
  Pers.WebPasswort,

  WH.Wohnheim_ID,
  WH.Suchname as Wohnheim_Suchname,
  WH.Name as Wohnheim_Name,

  VO.VO_ID,
  VO.Suchname as VO_Suchname,

  PVV.Art,
  PVV.Beginn,
  PVV.Ende,
  PVV.PERSPERSONENARTID,
  PVV.Vertragsart_ID,
  PVV.Status,
  PVV.StatusName
from TLS.Person Pers
join TLS.PersVV2 PVV
  on Pers.Mandant_Id = PVV.Mandant_ID
 and Pers.Person_Id = PVV.Person_ID
join TLS.VO VO
  on PVV.Mandant_Id = VO.Mandant_Id
 and PVV.VO_ID = VO.VO_ID
left join TLS.Wohnheim WH
  on WH.Mandant_Id = PVV.Mandant_ID
 and WH.Wohnheim_ID = PVV.Wohnheim_ID
where Pers.Mandant_ID = TLS.GetMandantID
  and VO.VOArt_ID not in (42,43,44,45)
  and substr(VO.Suchname,1,3) between 810 and 850
  and PVV.Ende > trunc(sysdate)-30
  and PVV.Status = 2
