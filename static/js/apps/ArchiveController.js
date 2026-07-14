// Controller mínimo apenas para montar o app Vue e remover o v-cloak.
// A página de arquivo é renderizada no servidor; não precisa de reatividade.
registerController('ArchiveController', () => {
    return {};
});
