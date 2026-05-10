// BITE.co Frontend Configuration
// Update these URLs for production (S3 + ALB deployment)
//
// URLs de microservicios (ALB) — para pruebas locales con backend en AWS
// En producción, estos endpoints deben apuntar a HTTPS + ACM.
// Los Urls cambian en cada depliegue de terraform, actualizar al momento de desplegar
//
const CONFIG = {
  AUTH_URL: 'http://bite2-alb-649890512.us-east-1.elb.amazonaws.com',
  USUARIOS_URL: 'http://bite2-alb-649890512.us-east-1.elb.amazonaws.com',
  CLOUD_URL: 'http://bite2-alb-649890512.us-east-1.elb.amazonaws.com',
  REPORTES_URL: 'http://bite2-alb-649890512.us-east-1.elb.amazonaws.com',
  SEGURIDAD_URL: 'http://bite2-alb-649890512.us-east-1.elb.amazonaws.com',
};
