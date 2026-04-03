SELECT
  CASE 
    WHEN taxon_id = 'GymPiPiPnCx50820-00' THEN 'Radiata'
    WHEN taxon_id IN ('GymPiPiPdCr50620-00', 'GymPiPiPdCr50498-00', 'GymPiPiPdCr50613-00', 'GymPiPiPdCr50626-00', 'GymPiPiPdCr50563-00', 'GymPiPiPhYa50637-00', 'GymPiPiPhYa50636-00', 'GymPiPiPdCr50488-00') THEN 'Native Gymnosperm'
    WHEN taxon_id IN ('AngMaGeRbCx16511-00', 'AngMaMaVlCx32870-00', 'AngMaLaMnMc23983-00', 'AngMaPrPrTc42455-00', 'AngMaAsRsSc01578-00', 'AngMaAsStRc01661-00', 'AngMaOxLcRp41599-00', 'AngMaLaLrCx22033-00', 'AngMaOxLcRp41492-00', 'AngMaMyMyRt38981-00') THEN 'Top10 Native Angiosperm'
    ELSE 'Other'
  END as group_name,
  COUNT(1) as total_nz,
  SUM(CASE WHEN ST_DISTANCE(ST_GEOGPOINT(longitude, latitude), ST_GEOGPOINT(175.09968969862783, -41.151583464812404)) < 5000 THEN 1 ELSE 0 END) as within_5km,
  SUM(CASE WHEN ST_DISTANCE(ST_GEOGPOINT(longitude, latitude), ST_GEOGPOINT(175.09968969862783, -41.151583464812404)) < 25000 THEN 1 ELSE 0 END) as within_25km,
  SUM(CASE WHEN ST_DISTANCE(ST_GEOGPOINT(longitude, latitude), ST_GEOGPOINT(175.09968969862783, -41.151583464812404)) < 50000 THEN 1 ELSE 0 END) as within_50km
FROM `treekipedia-479918.species_data.sinr_v41_preview_strict_core_train_v1`
WHERE latitude < -34 AND latitude > -47 AND longitude > 166 AND longitude < 179
GROUP BY 1
ORDER BY 1
