# Liquidaciones y vouchers históricos — 2026-10-10

- Restaurado botón Nueva liquidación: selección de pendientes dentro del panel lateral, sin formulario duplicado en la página.
- Los históricos con voucher muestran «Voucher presentado · Por revisar». Se conserva el estado original; un OCR coincidente no equivale a aprobación bancaria.
- Ver voucher abre la imagen o PDF dentro del panel. No se requiere otra carga de archivos históricos.
- Auditoría de Laravel y V2: cuatro vouchers de S/ 55, liquidaciones originales 1, 3, 10 y 21. Los cuatro archivos de V2 coinciden por SHA-256 con sus originales y sus emisiones tienen active_key de vendedor: quedan excluidas de nuevas liquidaciones.
- Laravel mantiene esas cuatro liquidaciones en pending, sin approved_at ni liquidated_at. No se modificaron estados financieros ni se duplicaron vouchers.
- La central de documentos original no contiene vouchers adicionales. Pendientes sin liquidación de vendedor: A-00001 (55), B-00001 (255), B-00002 (255), A-00005 (55), A-00008 (55): total S/ 675, sujeto al alcance comercial de cada usuario.
- Validación: tipos TypeScript, ESLint de componentes modificados y compilación de publicación. Revisión remota de relaciones, integridad de archivos y exclusión de pendientes.
